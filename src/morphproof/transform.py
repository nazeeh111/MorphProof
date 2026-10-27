"""A deliberately small, fail-closed Python numeric-kernel to Rust compiler.

This module translates a declared subset, not arbitrary Python. Verification is
still required: successful compilation is not an equivalence claim.
"""
from __future__ import annotations

import ast
import hashlib
import json
import keyword
import re
import os
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import sysconfig
import time


class UnsupportedSource(ValueError):
    """The source or contract falls outside the supported transformation subset."""


_LIMITS = [
    "One positional list[float] parameter and a float result per declared function.",
    "Only numeric local variables initialized with float expressions; no integer arithmetic.",
    "No imports, global reads, decorators, recursion, side effects, mutation, generators, or dynamic calls in kernels.",
    "Supported: float +, -, *, /; comparisons; boolean conditions; abs; len; if; for over the input or its constant slices; constant indexing; literal exceptions.",
    "Python and Rust binary64 operations run without fast-math; empirical verification is required on each target platform.",
    "Outside the declared list-of-floats domain, Python argument conversion and exception behavior may differ.",
]


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _rust_string(value: str) -> str:
    pieces = []
    for character in value:
        if character == '"':
            pieces.append('\\"')
        elif character == "\\":
            pieces.append("\\\\")
        elif ord(character) < 32 or ord(character) == 127:
            pieces.append("\\u{" + format(ord(character), "x") + "}")
        else:
            pieces.append(character)
    return '"' + "".join(pieces) + '"'


class _Lower:
    def __init__(self, node: ast.FunctionDef, parameter: str):
        self.node, self.parameter = node, parameter
        self.locals: set[str] = set()
        self.shadowed = {item.id for item in ast.walk(node) if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store)}
        self.indent = 1

    def fail(self, node: ast.AST, message: str):
        raise UnsupportedSource(f"{self.node.name}:{getattr(node, 'lineno', '?')}: {message}")

    def local(self, name: str) -> str:
        return "v_" + name

    def expr(self, node: ast.AST, assigned: set[str]) -> tuple[str, str]:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            if isinstance(node.value, int) and abs(node.value) > 2**53:
                self.fail(node, "integer literals larger than 2**53 are unsupported")
            value = float(node.value)
            if not (-float('inf') < value < float('inf')):
                self.fail(node, "nonfinite numeric literals are unsupported")
            return f"{repr(value)}_f64", "float" if type(node.value) is float else "int"
        if isinstance(node, ast.Name):
            if node.id == self.parameter:
                self.fail(node, "the list parameter may only be iterated, indexed, or passed to len")
            if node.id not in assigned:
                self.fail(node, f"read of uninitialized or external variable {node.id!r}")
            return self.local(node.id), "float"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            # Python -0 is integer zero, whereas -0.0 has a sign bit.
            if isinstance(node.operand, ast.Constant) and type(node.operand.value) is int:
                integer = -node.operand.value if isinstance(node.op, ast.USub) else node.operand.value
                return self.expr(ast.Constant(value=integer), assigned)
            value, typ = self.expr(node.operand, assigned)
            return (f"(-{value})" if isinstance(node.op, ast.USub) else f"({value})"), typ
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            lhs, lt = self.expr(node.left, assigned)
            rhs, rt = self.expr(node.right, assigned)
            if lt == rt == "int":
                self.fail(node, "integer arithmetic is outside the float-kernel subset")
            if isinstance(node.op, ast.Div):
                return f"mp_div({lhs}, {rhs})?", "float"
            op = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*'}[type(node.op)]
            return f"({lhs} {op} {rhs})", "float"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords and len(node.args) == 1:
            if node.func.id == self.parameter or node.func.id in self.shadowed:
                self.fail(node, "calls through a shadowed builtin are unsupported")
            if node.func.id == "len" and isinstance(node.args[0], ast.Name) and node.args[0].id == self.parameter:
                return "(values.len() as f64)", "int"
            if node.func.id == "abs":
                value, typ = self.expr(node.args[0], assigned)
                if typ != "float":
                    self.fail(node, "abs requires a float expression")
                return f"({value}).abs()", "float"
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == self.parameter:
            index = self.integer(node.slice)
            return f"mp_index(&values, {index}_i64)?", "float"
        self.fail(node, f"unsupported expression {type(node).__name__}")

    def integer(self, node: ast.AST) -> int:
        if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) <= 2**53:
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) and isinstance(node.operand, ast.Constant) and type(node.operand.value) is int and abs(node.operand.value) <= 2**53:
            return -node.operand.value
        self.fail(node, "index and slice bounds must be integer literals")

    def condition(self, node: ast.AST, assigned: set[str]) -> str:
        if isinstance(node, ast.Compare):
            values = [self.expr(value, assigned)[0] for value in [node.left, *node.comparators]]
            ops = {ast.Eq: '==', ast.NotEq: '!=', ast.Lt: '<', ast.LtE: '<=', ast.Gt: '>', ast.GtE: '>='}
            if any(type(op) not in ops for op in node.ops):
                self.fail(node, "only numeric order/equality comparisons are supported")
            return " && ".join(f"({values[i]} {ops[type(op)]} {values[i+1]})" for i, op in enumerate(node.ops))
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            op = " && " if isinstance(node.op, ast.And) else " || "
            return "(" + op.join(self.condition(value, assigned) for value in node.values) + ")"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return "!(" + self.condition(node.operand, assigned) + ")"
        value, _ = self.expr(node, assigned)
        # NaN is truthy in Python, so != 0.0 is intentional.
        return f"({value} != 0.0)"

    def iterable(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name) and node.id == self.parameter:
            return "values.iter().copied()"
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == self.parameter and isinstance(node.slice, ast.Slice):
            slc = node.slice
            if slc.step is not None and self.integer(slc.step) != 1:
                self.fail(node, "slice steps other than 1 are unsupported")
            lower = "None" if slc.lower is None else f"Some({self.integer(slc.lower)}_i64)"
            upper = "None" if slc.upper is None else f"Some({self.integer(slc.upper)}_i64)"
            return f"mp_slice(&values, {lower}, {upper}).iter().copied()"
        self.fail(node, "for loops must iterate over the input list or its constant slice")

    def emit(self, line: str) -> str:
        return "    " * self.indent + line + "\n"

    def block(self, statements: list[ast.stmt], assigned: set[str]) -> tuple[str, set[str], bool]:
        out = ""
        terminated = False
        for stmt in statements:
            if terminated:
                self.fail(stmt, "unreachable statements are unsupported")
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
                continue
            if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 and isinstance(stmt.targets[0], ast.Name):
                name = stmt.targets[0].id
                if name == self.parameter:
                    self.fail(stmt, "input reassignment is unsupported")
                value, typ = self.expr(stmt.value, assigned)
                if typ != "float":
                    self.fail(stmt, "numeric locals must be initialized with a float expression (use 0.0 rather than 0)")
                self.locals.add(name)
                assigned.add(name)
                out += self.emit(f"{self.local(name)} = {value};")
            elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                value, _ = self.expr(ast.BinOp(left=stmt.target, op=stmt.op, right=stmt.value), assigned)
                out += self.emit(f"{self.local(stmt.target.id)} = {value};")
            elif isinstance(stmt, ast.Return) and stmt.value is not None:
                value, typ = self.expr(stmt.value, assigned)
                if typ != "float":
                    self.fail(stmt, "return value must be a float expression")
                out += self.emit(f"return Ok({value});")
                terminated = True
            elif isinstance(stmt, ast.Raise) and stmt.cause is None and isinstance(stmt.exc, ast.Call) and isinstance(stmt.exc.func, ast.Name) and stmt.exc.func.id in ("ValueError", "ZeroDivisionError", "IndexError", "TypeError", "OverflowError") and len(stmt.exc.args) == 1 and not stmt.exc.keywords and isinstance(stmt.exc.args[0], ast.Constant) and isinstance(stmt.exc.args[0].value, str):
                if stmt.exc.func.id == self.parameter or stmt.exc.func.id in self.shadowed:
                    self.fail(stmt, "raising through a shadowed builtin exception is unsupported")
                out += self.emit(f"return Err(pyo3::exceptions::Py{stmt.exc.func.id}::new_err({_rust_string(stmt.exc.args[0].value)}));")
                terminated = True
            elif isinstance(stmt, ast.If):
                cond = self.condition(stmt.test, assigned)
                out += self.emit(f"if {cond} {{")
                self.indent += 1
                yes, ya, yt = self.block(stmt.body, set(assigned))
                self.indent -= 1
                out += yes + self.emit("} else {")
                self.indent += 1
                no, na, nt = self.block(stmt.orelse, set(assigned))
                self.indent -= 1
                out += no + self.emit("}")
                assigned = na if yt else ya if nt else ya & na
                terminated = yt and nt
            elif isinstance(stmt, ast.For) and isinstance(stmt.target, ast.Name) and not stmt.orelse:
                name = stmt.target.id
                if name == self.parameter:
                    self.fail(stmt, "loop target may not replace the input parameter")
                iterable = self.iterable(stmt.iter)
                self.locals.add(name)
                out += self.emit(f"for mp_item in {iterable} {{")
                self.indent += 1
                out += self.emit(f"{self.local(name)} = mp_item;")
                body, _, _ = self.block(stmt.body, assigned | {name})
                out += body
                self.indent -= 1
                out += self.emit("}")
            else:
                self.fail(stmt, f"unsupported statement {type(stmt).__name__}")
        return out, assigned, terminated

    def lower(self) -> str:
        args = self.node.args
        if self.node.decorator_list or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg or args.defaults or len(args.args) != 1 or args.args[0].arg != self.parameter:
            self.fail(self.node, "functions must have exactly the declared positional parameter and no defaults or decorators")
        body, _, terminal = self.block(self.node.body, set())
        if not terminal:
            self.fail(self.node, "every reachable path must return a float or raise a supported exception")
        declarations = "".join(self.emit(f"let mut {self.local(name)}: f64;") for name in sorted(self.locals))
        return f'#[pyfunction(name = {_rust_string(self.node.name)})]\nfn mp_{self.node.name}(values: Vec<f64>) -> PyResult<f64> {{\n' + declarations + body + "}\n"


_HELPERS = r'''
fn mp_div(a: f64, b: f64) -> PyResult<f64> {
    if b == 0.0 { return Err(pyo3::exceptions::PyZeroDivisionError::new_err("float division by zero")); }
    Ok(a / b)
}
fn mp_index(values: &[f64], index: i64) -> PyResult<f64> {
    let n = values.len() as i64;
    let i = if index < 0 { n + index } else { index };
    if i < 0 || i >= n { return Err(pyo3::exceptions::PyIndexError::new_err("list index out of range")); }
    Ok(values[i as usize])
}
fn mp_slice(values: &[f64], start: Option<i64>, stop: Option<i64>) -> &[f64] {
    let n = values.len() as i64;
    let bound = |i: i64| if i < 0 { (n + i).max(0) } else { i.min(n) };
    let a = start.map(bound).unwrap_or(0) as usize;
    let b = stop.map(bound).unwrap_or(n) as usize;
    &values[a..b.max(a)]
}
'''


def generate(reference: Path, contract: dict, *, source: str | None = None) -> str:
    """Validate the entire supported input, then return a Rust source string."""
    tree = ast.parse(Path(reference).read_text(encoding="utf-8") if source is None else source, filename=str(reference))
    definitions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    # Global effects make a frozen behavioral baseline harder to interpret.
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            if node.decorator_list or node.args.defaults or any(value is not None for value in node.args.kw_defaults):
                raise UnsupportedSource(f"module:{node.lineno}: decorators and function defaults are unsupported")
            annotations = [arg.annotation for arg in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs] if arg.annotation is not None]
            if node.returns is not None:
                annotations.append(node.returns)
            for annotation in annotations:
                allowed = isinstance(annotation, ast.Name) and annotation.id in {"float", "int", "list"}
                allowed = allowed or (isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name) and annotation.value.id == "list" and isinstance(annotation.slice, ast.Name) and annotation.slice.id == "float")
                if not allowed:
                    raise UnsupportedSource(f"module:{node.lineno}: annotations must be simple numeric types")
        if not isinstance(node, ast.FunctionDef) and not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            raise UnsupportedSource(f"module:{getattr(node, 'lineno', '?')}: only function definitions and a module docstring are supported")
    specs = contract.get("functions", [])
    if not specs or contract.get("schema") != 1:
        raise UnsupportedSource("contract schema must be 1 and functions must be nonempty")
    if any(not isinstance(spec, dict) for spec in specs):
        raise UnsupportedSource("each function contract must be an object")
    names = [spec.get("name") for spec in specs]
    if any(not isinstance(name, str) or not name.isidentifier() for name in names):
        raise UnsupportedSource("contract function names must be Python identifiers")
    supported_builtins = {"len", "abs", "ValueError", "ZeroDivisionError", "IndexError", "TypeError", "OverflowError"}
    if set(definitions) & supported_builtins:
        raise UnsupportedSource("module functions may not shadow supported builtins or exception types")
    if len(names) != len(set(names)):
        raise UnsupportedSource("contract function names must be unique")
    code = "// Generated by MORPHPROOF. Compilation does not establish compatibility.\nuse pyo3::prelude::*;\n" + _HELPERS
    for spec in specs:
        if spec.get("input") != "list[float]" or spec.get("output") != "float":
            raise UnsupportedSource("supported contract types are list[float] -> float")
        name, parameter = spec.get("name"), spec.get("parameter", "values")
        if not isinstance(parameter, str) or not parameter.isidentifier():
            raise UnsupportedSource("contract parameters must be Python identifiers")
        if name not in definitions:
            raise UnsupportedSource(f"declared function {name!r} not found")
        code += "\n" + _Lower(definitions[name], parameter).lower()
    code += '\n#[pymodule]\nfn _morphproof_native(m: &Bound<\'_, PyModule>) -> PyResult<()> {\n'
    code += "".join(f"    m.add_function(wrap_pyfunction!(mp_{name}, m)?)?;\n" for name in names)
    return code + "    Ok(())\n}\n"


def build_candidate(destination: Path, timeout: float = 300.0) -> dict:
    """Build an already generated crate and expose it as candidate.py."""
    destination = Path(destination).resolve()
    cargo = shutil.which("cargo")
    if cargo is None:
        raise RuntimeError("Rust cargo is required. Install the free Rust toolchain from https://rustup.rs/ and put cargo on PATH.")
    start = time.perf_counter()
    input_names = ["src/lib.rs", "Cargo.toml", "build.rs", "candidate.py", "pyproject.toml"]
    input_names.extend(str(path.relative_to(destination)) for path in (destination / "python").glob("*/__init__.py"))
    build_inputs = {name: _digest((destination / name).read_bytes()) for name in input_names}
    env = dict(os.environ)
    env["PYO3_PYTHON"] = sys.executable
    try:
        result = subprocess.run([cargo, "build", "--release", "--manifest-path", str(destination / "Cargo.toml"), "--target-dir", str(destination / "target")], cwd=destination, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        captured = exc.stdout or b""
        (destination / "build.log").write_text(captured.decode(errors="replace") if isinstance(captured, bytes) else captured, encoding="utf-8")
        raise RuntimeError(f"Rust build timed out after {timeout}s; see {destination / 'build.log'}") from exc
    (destination / "build.log").write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"Rust build failed; see {destination / 'build.log'}")
    if any(_digest((destination / name).read_bytes()) != digest for name, digest in build_inputs.items()):
        raise RuntimeError("candidate source or build configuration changed during compilation; rebuild from stable inputs")
    native_name = "_morphproof_native" + (sysconfig.get_config_var("EXT_SUFFIX") or ".so")
    suffix = ".dylib" if sys.platform == "darwin" else ".dll" if sys.platform == "win32" else ".so"
    library = destination / "target" / "release" / (("" if sys.platform == "win32" else "lib") + "_morphproof_native" + suffix)
    if not library.is_file():
        raise RuntimeError(f"cargo completed without the expected native library: {library}")
    native = destination / native_name
    shutil.copy2(library, native)
    result = {"candidate": str(destination / "candidate.py"), "native": str(native), "build_seconds": time.perf_counter() - start, "native_sha256": _digest(native.read_bytes()), "rust_sha256": _digest((destination / "src" / "lib.rs").read_bytes()), "built": True}
    artifacts = [native.name, *input_names, "Cargo.lock"]
    (destination / "morphproof-build.json").write_text(json.dumps({"schema": 1, "artifacts": artifacts}, indent=2) + "\n", encoding="utf-8")
    result["python"] = sys.version
    result["platform"] = platform.platform()
    for key, executable in (("cargo_version", cargo), ("rustc_version", shutil.which("rustc"))):
        try:
            result[key] = subprocess.check_output([executable, "--version"], text=True, env=env).strip() if executable else "unavailable"
        except (OSError, subprocess.CalledProcessError):
            result[key] = "unavailable"
    manifest_path = destination / "manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.update(result)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return result


def transform(reference: Path, destination: Path, contract: dict, buggy: bool = False, build: bool = True) -> dict:
    """Translate a declared float kernel, optionally compile it, and return provenance.

    Existing nonempty destinations are rejected. There is no fallback to Python.
    The deprecated ``buggy`` argument is rejected: demo mutations must be explicit
    artifacts, not a mode that silently changes normal transformation behavior.
    """
    reference, destination = Path(reference).resolve(), Path(destination).resolve()
    if buggy:
        raise ValueError("Inject demo defects explicitly into a separate candidate artifact")
    source_bytes = reference.read_bytes()
    contract_bytes = (json.dumps(contract, sort_keys=True, indent=2) + "\n").encode()
    rust = generate(reference, contract, source=source_bytes.decode("utf-8"))
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"destination must be absent or empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "src").mkdir()
    (destination / "src" / "lib.rs").write_text(rust, encoding="utf-8")
    (destination / "build.rs").write_text('fn main() { pyo3_build_config::add_extension_module_link_args(); }\n', encoding="utf-8")
    (destination / "Cargo.toml").write_text('[package]\nname = "morphproof-candidate"\nversion = "0.1.0"\nedition = "2021"\n\n[lib]\nname = "_morphproof_native"\ncrate-type = ["cdylib"]\n\n[dependencies]\npyo3 = { version = "=0.27.2", features = ["extension-module", "abi3-py310"] }\n\n[build-dependencies]\npyo3-build-config = "=0.27.2"\n', encoding="utf-8")
    package_import = reference.stem if reference.stem.isidentifier() and not keyword.iskeyword(reference.stem) else "morphproof_candidate"
    distribution = (re.sub(r"[^A-Za-z0-9]+", "-", reference.stem).strip("-") or "candidate") + "-morphproof"
    (destination / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["maturin>=1.9,<2"]\nbuild-backend = "maturin"\n\n[project]\n'
        + f'name = "{distribution}"\nversion = "0.1.0"\nrequires-python = ">=3.10"\n\n[tool.maturin]\n'
        + f'python-source = "python"\nmodule-name = "{package_import}._morphproof_native"\n', encoding="utf-8")
    (destination / "reference.py").write_bytes(source_bytes)
    (destination / "contract.json").write_bytes(contract_bytes)
    used_names = {item["name"] for item in contract["functions"]} | {item.get("parameter", "values") for item in contract["functions"]}
    backend = "_morphproof_native_module"
    while backend in used_names:
        backend += "_"
    wrappers = "".join(
        f"def {spec['name']}({spec.get('parameter', 'values')}):\n"
        f"    return {backend}.{spec['name']}({spec.get('parameter', 'values')})\n\n"
        for spec in contract["functions"]
    )
    loader = '''"""Load this candidate's compiled Rust extension by absolute path."""
import importlib.util as _util
from pathlib import Path as _Path
import sysconfig as _sysconfig
_path = _Path(__file__).parent / ("_morphproof_native" + (_sysconfig.get_config_var("EXT_SUFFIX") or ".so"))
_spec = _util.spec_from_file_location("_morphproof_native", _path)
'''
    loader += f"{backend} = _util.module_from_spec(_spec)\n_spec.loader.exec_module({backend})\n" + wrappers
    package_dir = destination / "python" / package_import
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text(
        '"""Rust-backed Python package generated by MORPHPROOF."""\n'
        + f"from . import _morphproof_native as {backend}\n\n" + wrappers, encoding="utf-8")
    (destination / "candidate.py").write_text(loader, encoding="utf-8")
    manifest = {"schema": 1, "kind": "bounded-ast-to-rust", "reference": str(reference), "reference_sha256": _digest(source_bytes), "contract_sha256": _digest(contract_bytes), "rust_sha256": _digest(rust.encode()), "candidate": str(destination / "candidate.py"), "source": str(destination / "src" / "lib.rs"), "limitations": _LIMITS, "package_import": package_import, "distribution": distribution, "built": False}
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    if build:
        manifest.update(build_candidate(destination))
        manifest["built"] = True
        (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest
