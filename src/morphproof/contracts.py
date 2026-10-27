"""Explicit, reviewable contract discovery. No inferred universal guarantees."""
import ast
import json
from pathlib import Path


def discover(reference: Path) -> dict:
    tree = ast.parse(Path(reference).read_text())
    functions = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            if len(node.args.args) == 1:
                functions.append(dict(name=node.name, parameter=node.args.args[0].arg,
                    input="list[float]", output="float", max_length=256, rtol=0.0, atol=0.0))
    if not functions:
        raise ValueError("No public single-argument functions found")
    return dict(schema=1, objective="Review the declared domain before verification", functions=functions,
                discovery={"kind":"AST signature inventory", "requires_review":True,
                           "note":"Types and domain are a proposed bounded contract, not inferred facts."})


def load_contract(path: Path) -> dict:
    data = json.loads(Path(path).read_text())
    if not isinstance(data, dict) or data.get("schema") != 1 or not isinstance(data.get("functions"), list) or not data["functions"]:
        raise ValueError("Expected schema 1 with a nonempty functions array")
    names = set()
    for f in data["functions"]:
        if not isinstance(f, dict):
            raise ValueError("Each function contract must be a JSON object")
        name = f.get("name", "")
        if not isinstance(name, str) or not name.isidentifier() or name in names:
            raise ValueError("Function names must be unique Python identifiers")
        names.add(name)
        parameter = f.get("parameter", "values")
        if not isinstance(parameter, str) or not parameter.isidentifier():
            raise ValueError("parameter must be a Python identifier")
        if not isinstance(f.get("allow_nonfinite", True), bool):
            raise ValueError("allow_nonfinite must be a boolean")
        if f.get("input") != "list[float]" or f.get("output") != "float":
            raise ValueError("Supported contract: list[float] -> float")
        if isinstance(f.get("max_length", 256), bool) or not isinstance(f.get("max_length", 256), int) or not 0 <= f.get("max_length", 256) <= 10000:
            raise ValueError("max_length must be an integer from 0 to 10000")
        for key in ("rtol", "atol"):
            value = f.get(key, 0.)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value < float("inf"):
                raise ValueError(key + " must be finite and nonnegative")
    return data
