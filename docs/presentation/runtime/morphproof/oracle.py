"""Independent, bounded differential execution for declared numeric contracts.

A compatible report is finite empirical evidence, never universal equivalence.
Subjects must be trusted: child processes constrain time, not filesystem access.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import queue
import subprocess
import sys
import threading

from .inputs import Selector
from .worker import decode, encode


class Worker:
    def __init__(self, path: Path, timeout: float = 3.0):
        self.path, self.timeout = Path(path).resolve(), timeout
        self.process = None
        self.messages = queue.Queue()
        self.reader = None
        self.error = None
        try:
            self.process = subprocess.Popen(
                [sys.executable, "-I", str(Path(__file__).with_name("worker.py")), str(self.path)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=self.path.parent,
            )
            self.reader = threading.Thread(target=self._read_lines, daemon=True)
            self.reader.start()
            ready = self._read()
            if not ready.get("ready"):
                self.error = ready.get("error", {"kind": "load_error", "message": "worker did not become ready"})
        except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            self.error = {"kind": "load_error", "type": type(exc).__name__, "message": str(exc)}
            self.close()

    def _read_lines(self):
        try:
            while True:
                line = self.process.stdout.readline(8 * 1024 * 1024 + 1)
                if not line:
                    self.messages.put(OSError("worker exited before responding"))
                    return
                if len(line) > 8 * 1024 * 1024:
                    self.messages.put(ValueError("subject response exceeded 8 MiB limit"))
                    return
                self.messages.put(line)
        except (OSError, ValueError) as exc:
            self.messages.put(exc)

    def _read(self):
        try:
            line = self.messages.get(timeout=self.timeout)
        except queue.Empty as exc:
            raise TimeoutError(f"subject exceeded {self.timeout:g}s response limit") from exc
        if isinstance(line, Exception):
            raise line
        return json.loads(line)

    def call(self, function: str, values: list[float], trace=False, keyword=None):
        if self.error:
            return {"outcome": self.error, "lines": [], "arcs": []}
        try:
            request = {"function": function, "values": encode(values), "trace": trace, "keyword": keyword}
            self.process.stdin.write((json.dumps(request, allow_nan=False) + "\n").encode())
            self.process.stdin.flush()
            return self._read()
        except (BrokenPipeError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            kind = "timeout" if isinstance(exc, TimeoutError) else "worker_error"
            self.error = {"kind": kind, "type": type(exc).__name__, "message": str(exc)}
            self.close()
            return {"outcome": self.error, "lines": [], "arcs": []}

    def close(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait()
            for pipe in (self.process.stdin, self.process.stdout):
                if pipe is not None:
                    pipe.close()
        if self.reader is not None:
            self.reader.join(timeout=.1)


def _float_equal(left: float, right: float, rtol: float, atol: float) -> bool:
    if math.isnan(left) or math.isnan(right):
        return math.isnan(left) and math.isnan(right)
    if math.isinf(left) or math.isinf(right):
        return left == right
    if left == 0 and right == 0:
        return math.copysign(1, left) == math.copysign(1, right)
    return math.isclose(left, right, rel_tol=rtol, abs_tol=atol)


def equivalent(left: dict, right: dict, rtol=0.0, atol=0.0) -> bool:
    """Compare return type, signed zero, nonfinite results, and exception identity/message."""
    if left.get("kind") != right.get("kind"):
        return False
    if left.get("kind") == "exception":
        return left.get("type") == right.get("type") and left.get("message") == right.get("message")
    if left.get("kind") != "return" or left.get("type") != right.get("type"):
        return False
    a, b = decode(left.get("value")), decode(right.get("value"))
    if left.get("type") == "float":
        return _float_equal(a, b, rtol, atol)
    return a == b


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _artifact_hashes(candidate):
    """Hash an optional local build manifest without following artifact symlinks."""
    root = candidate.parent
    manifest = root / "morphproof-build.json"
    if not manifest.exists():
        return {}
    if manifest.is_symlink():
        raise ValueError("build manifest must not be a symlink")
    data = json.loads(manifest.read_text())
    paths = data.get("artifacts")
    if not isinstance(paths, list) or not paths or len(paths) > 100:
        raise ValueError("build manifest artifacts must contain 1 to 100 relative paths")
    hashes = {"morphproof-build.json": _hash(manifest)}
    for value in paths:
        if not isinstance(value, str):
            raise ValueError("build artifact paths must be strings")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("build artifact paths must stay within the candidate directory")
        path = root / relative
        if any(part.is_symlink() for part in [path, *path.parents] if part != root and root in part.parents):
            raise ValueError("build artifact paths must not contain symlinks")
        if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"build artifact is missing or outside the candidate directory: {value}")
        hashes[relative.as_posix()] = _hash(path)
    return hashes


def _validate(contract, budget, seed):
    if isinstance(budget, bool) or not isinstance(budget, int) or not 1 <= budget <= 100000:
        raise ValueError("budget must be an integer between 1 and 100000 per function")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if not isinstance(contract, dict) or type(contract.get("schema")) is not int or contract.get("schema") != 1:
        raise ValueError("contract schema must be 1")
    functions = contract.get("functions")
    if not isinstance(functions, list) or not functions:
        raise ValueError("contract must declare at least one function")
    names = set()
    for item in functions:
        if not isinstance(item, dict):
            raise ValueError("each declared function must be an object")
        name = item.get("name")
        if not isinstance(name, str) or not name.isidentifier() or name in names:
            raise ValueError("function names must be unique Python identifiers")
        names.add(name)
        if not isinstance(item.get("parameter", "values"), str) or not item.get("parameter", "values").isidentifier():
            raise ValueError("parameter must be a Python identifier")
        if not isinstance(item.get("allow_nonfinite", True), bool):
            raise ValueError("allow_nonfinite must be a boolean")
        if item.get("input") != "list[float]" or item.get("output") != "float":
            raise ValueError("supported contract is one list[float] argument and float result")
        length = item.get("max_length", 256)
        if isinstance(length, bool) or not isinstance(length, int) or not 0 <= length <= 10000:
            raise ValueError("max_length must be an integer between 0 and 10000")
        for key in ("rtol", "atol"):
            tolerance = item.get(key, 0.0)
            if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or not math.isfinite(tolerance) or tolerance < 0:
                raise ValueError(f"{key} must be finite and nonnegative")


def _shrink(values, mismatch, remaining):
    """Delta-debug list length, then simplify scalars without exceeding call cap."""
    current, used = list(values), 0
    granularity = 2
    while current and used < remaining:
        size = max(1, math.ceil(len(current) / granularity))
        reduced = False
        for start in range(0, len(current), size):
            candidate = current[:start] + current[start + size:]
            used += 1
            if mismatch(candidate):
                current, reduced = candidate, True
                granularity = max(2, granularity - 1)
                break
            if used >= remaining:
                break
        if reduced:
            continue
        if granularity >= len(current):
            break
        granularity = min(len(current), granularity * 2)
    # A one-way simplification order prevents cycling between equal-complexity values.
    simple = [0.0, -0.0, 1.0, -1.0]
    for index in range(len(current)):
        original = current[index]
        if not math.isfinite(original):
            continue
        for value in simple:
            if value == original and math.copysign(1, value) == math.copysign(1, original):
                break
            if used >= remaining:
                break
            candidate = current.copy()
            candidate[index] = value
            used += 1
            if mismatch(candidate):
                current = candidate
                break
    return current, used


def _atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def verify(reference: Path, candidate: Path, contract: dict, output: Path, budget=128, seed=0, strategy="boundary") -> dict:
    """Execute independently selected cases against trusted Python module files.

    ``budget`` counts differential challenge pairs per function. Minimization has
    a separate maximum of 128 pairs per function, reported independently. Source
    hashes are checked before and after execution. Dependencies are not frozen.
    """
    contract = deepcopy(contract)
    _validate(contract, budget, seed)
    reference, candidate, output = Path(reference).resolve(), Path(candidate).resolve(), Path(output)
    if not reference.is_file() or not candidate.is_file():
        raise ValueError("reference and candidate must be existing Python module files")
    if reference == candidate:
        raise ValueError("reference and candidate must be different files")
    if (output / "report.json").exists():
        raise FileExistsError("evidence report already exists; choose a fresh output directory")
    output.mkdir(parents=True, exist_ok=True)
    source = reference.read_text()
    ref_hash, cand_hash = _hash(reference), _hash(candidate)
    artifact_hashes = _artifact_hashes(candidate)
    provenance = {
        "reference": str(reference), "candidate": str(candidate),
        "reference_sha256": ref_hash, "candidate_sha256": cand_hash,
        "contract_sha256": hashlib.sha256(json.dumps(contract, sort_keys=True, allow_nan=False).encode()).hexdigest(),
        "seed": seed, "strategy": strategy, "budget": budget, "budget_unit": "differential challenge pairs per function",
        "python": sys.version.split()[0], "timeout_seconds": 3.0,
        "artifact_sha256": artifact_hashes,
    }
    # Snapshot individual source bytes, never copy an unbounded repository.
    (output / "reference.snapshot.py").write_bytes(reference.read_bytes())
    (output / "candidate.snapshot.py").write_bytes(candidate.read_bytes())
    _atomic_json(output / "contract.snapshot.json", contract)
    report = {
        "schema": 1, "status": "compatible", "functions": [], "provenance": provenance,
        "totals": {"tested": 0, "failures": 0, "shrink_executions": 0, "api_tested": 0, "api_failures": 0, "unique_inputs": 0},
        "claims": {"verified": [], "failed": [], "untested": [
            "Universal equivalence", "Inputs outside the declared domain", "Stateful or nondeterministic behavior",
            "Dependency behavior beyond the captured source files", "Security isolation", "Performance improvements",
        ]},
        "limitations": [
            "Finite empirical testing is evidence of compatibility, not a proof of universal equivalence.",
            "Trusted code only: subprocess time limits do not sandbox filesystem, network, or memory access.",
            "Only one list of floats is generated; three bounded keyword-call checks supplement the main positional challenges. Unsupported types and other calling conventions are untested.",
            "Source snapshots cover the two module files and declared contract; an optional morphproof-build.json hashes declared native artifacts. Other imported dependencies are not frozen.",
            "Pure deterministic functions are assumed; each worker imports its module once and retains module state.",
            "NaN payload bits are not compared; signed zero, infinities, result types and exception type/message are compared.",
        ],
    }
    all_counterexamples = []
    tested_cases = []
    ref, cand = Worker(reference), Worker(candidate)
    try:
        for index, spec in enumerate(contract["functions"]):
            name = spec["name"]
            selector = Selector(source, spec.get("max_length", 256), seed + index, strategy, spec.get("allow_nonfinite", True))
            result = {"name": name, "status": "compatible", "tested": 0, "failures": 0,
                      "counterexamples": [], "shrink_executions": 0, "errors": [], "api_tested": 0, "api_failures": 0, "unique_inputs": 0}
            failure_signatures = set()
            unique_inputs = set()
            for case_index in range(budget):
                challenge = selector.next()
                left = ref.call(name, challenge.values, trace=True)
                right = cand.call(name, challenge.values)
                selector.observe(challenge, left)
                a, b = left["outcome"], right["outcome"]
                tested_cases.append({"function": name, "case_index": case_index, "family": challenge.family,
                                     "call": "positional", "input": encode(challenge.values), "reference": a, "candidate": b})
                unique_inputs.add(json.dumps(encode(challenge.values), sort_keys=True, allow_nan=False))
                result["tested"] += 1
                infrastructure_error = any(item.get("kind") not in {"return", "exception"} for item in (a, b))
                if infrastructure_error:
                    result["status"] = "error"
                    result["errors"].append({"input": encode(challenge.values), "reference": a, "candidate": b})
                    break
                if a.get("kind") == "return" and a.get("type") != spec["output"]:
                    result["status"] = "error"
                    result["errors"].append({"reason": "invalid_reference_contract", "message": f"declared {spec['output']} result, reference returned {a.get('type')}",
                                             "input": encode(challenge.values), "reference": a, "candidate": b})
                    break
                if equivalent(a, b, spec.get("rtol", 0.0), spec.get("atol", 0.0)):
                    continue
                result["failures"] += 1
                result["status"] = "incompatible"
                signature = (a.get("kind"), a.get("type"), a.get("message"), b.get("kind"), b.get("type"), b.get("message"), challenge.family)
                if signature in failure_signatures or len(result["counterexamples"]) >= 4:
                    continue
                failure_signatures.add(signature)
                observed = {}
                def mismatch(values):
                    x = ref.call(name, values)["outcome"]
                    y = cand.call(name, values)["outcome"]
                    if any(item.get("kind") not in {"return", "exception"} for item in (x, y)):
                        return False
                    if x.get("kind") == "return" and x.get("type") != spec["output"]:
                        return False
                    different = not equivalent(x, y, spec.get("rtol", 0.0), spec.get("atol", 0.0))
                    if different:
                        observed["reference"], observed["candidate"] = x, y
                    return different
                remaining = max(0, 128 - result["shrink_executions"])
                minimized, count = _shrink(challenge.values, mismatch, remaining)
                result["shrink_executions"] += count
                counterexample = {"function": name, "case_index": case_index, "family": challenge.family,
                                  "input": encode(challenge.values), "reference": a, "candidate": b,
                                  "minimized_input": encode(minimized), "minimization_calls": count,
                                  "minimized_reference": observed.get("reference", a),
                                  "minimized_candidate": observed.get("candidate", b)}
                result["counterexamples"].append(counterexample)
                all_counterexamples.append(counterexample)
            if result["status"] != "error":
                for values in [[], [0.0], [1.0, -1.0]]:
                    if len(values) > spec.get("max_length", 256):
                        continue
                    keyword = spec.get("parameter", "values")
                    left = ref.call(name, values, keyword=keyword)
                    right = cand.call(name, values, keyword=keyword)
                    a, b = left["outcome"], right["outcome"]
                    result["api_tested"] += 1
                    tested_cases.append({"function": name, "call": "keyword", "keyword": keyword,
                                         "input": encode(values), "reference": a, "candidate": b})
                    if any(item.get("kind") not in {"return", "exception"} for item in (a, b)):
                        result["status"] = "error"
                        result["errors"].append({"input": encode(values), "keyword": keyword, "reference": a, "candidate": b})
                        break
                    if left.get("binding_error"):
                        result["status"] = "error"
                        result["errors"].append({"reason": "invalid_reference_contract", "message": f"reference API cannot bind declared parameter {keyword!r}",
                                                 "binding_error": left["binding_error"], "input": encode(values), "keyword": keyword, "reference": a, "candidate": b})
                        break
                    if a.get("kind") == "return" and a.get("type") != spec["output"]:
                        result["status"] = "error"
                        result["errors"].append({"reason": "invalid_reference_contract", "message": f"declared {spec['output']} result, reference returned {a.get('type')}",
                                                 "input": encode(values), "keyword": keyword, "reference": a, "candidate": b})
                        break
                    if not equivalent(a, b, spec.get("rtol", 0.0), spec.get("atol", 0.0)):
                        result["status"] = "incompatible"
                        result["api_failures"] += 1
                        counterexample = {"function": name, "family": "keyword-api", "keyword": keyword,
                                          "input": encode(values), "minimized_input": encode(values),
                                          "reference": a, "candidate": b, "minimized_reference": a, "minimized_candidate": b,
                                          "minimization_calls": 0}
                        result["counterexamples"].append(counterexample)
                        all_counterexamples.append(counterexample)
            result["unique_inputs"] = len(unique_inputs)
            result["selection"] = selector.metrics()
            report["functions"].append(result)
            for key in ("tested", "failures", "shrink_executions", "api_tested", "api_failures", "unique_inputs"):
                report["totals"][key] += result[key]
            if result["status"] == "error":
                report["status"] = "error"
            elif result["status"] == "incompatible" and report["status"] != "error":
                report["status"] = "incompatible"
            claim = f"{name}: {result['tested']} positional cases and {result['api_tested']} keyword API checks, {result['failures'] + result['api_failures']} mismatches under the declared contract"
            report["claims"]["verified" if result["status"] == "compatible" else "failed"].append(claim)
    finally:
        ref.close()
        cand.close()
    try:
        unchanged = _hash(reference) == ref_hash and _hash(candidate) == cand_hash and _artifact_hashes(candidate) == artifact_hashes
    except (OSError, ValueError):
        unchanged = False
    report["provenance"]["sources_unchanged"] = unchanged
    if not unchanged:
        report["status"] = "error"
        report["claims"]["failed"].append("Source files changed during verification; acceptance invalidated")
    _atomic_json(output / "counterexamples.json", all_counterexamples)
    _atomic_json(output / "tested-cases.json", tested_cases)
    report["provenance"]["tested_cases_sha256"] = _hash(output / "tested-cases.json")
    report["artifacts"] = {"cases": "tested-cases.json", "counterexamples": "counterexamples.json",
                           "reference": "reference.snapshot.py", "candidate": "candidate.snapshot.py", "contract": "contract.snapshot.json", "replay": "replay.py"}
    (output / "replay.py").write_text('''"""Replay saved counterexamples against a repaired candidate.
Usage: python replay.py reference.py candidate.py
Requires an installed morphproof package.
"""
from pathlib import Path
import sys
from morphproof.oracle import replay_cases

if __name__ == "__main__":
    raise SystemExit(0 if replay_cases(Path(sys.argv[1]), Path(sys.argv[2]), Path(__file__).with_name("counterexamples.json"), Path(__file__).with_name("contract.snapshot.json")) else 1)
''')
    _atomic_json(output / "report.json", report)
    return report


def replay_cases(reference: Path, candidate: Path, cases: Path, contract: Path) -> bool:
    """Return whether the candidate now matches the reference on saved failures."""
    specs = {item["name"]: item for item in json.loads(Path(contract).read_text())["functions"]}
    records = json.loads(Path(cases).read_text())
    ref, cand = Worker(Path(reference)), Worker(Path(candidate))
    passed = True
    try:
        for record in records:
            name = record["function"]
            spec = specs[name]
            values = decode(record["minimized_input"])
            left = ref.call(name, values, keyword=record.get("keyword"))
            right = cand.call(name, values, keyword=record.get("keyword"))
            a, b = left["outcome"], right["outcome"]
            if left.get("binding_error") or (a.get("kind") == "return" and a.get("type") != spec["output"]) or not equivalent(a, b, spec.get("rtol", 0.0), spec.get("atol", 0.0)):
                passed = False
                print(json.dumps({"function": name, "input": encode(values), "reference": a, "candidate": b}, allow_nan=False))
    finally:
        ref.close()
        cand.close()
    return passed
