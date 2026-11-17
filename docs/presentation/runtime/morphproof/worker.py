"""Private JSON-lines worker. Process isolation is not a security sandbox."""
from __future__ import annotations

import contextlib
import importlib.util
import inspect
import io
import json
import math
from pathlib import Path
import sys
import time


def decode(value):
    if isinstance(value, dict) and set(value) == {"$float"}:
        return {"nan": float("nan"), "+inf": float("inf"), "-inf": -float("inf")}[value["$float"]]
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def encode(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {"$float": "nan" if math.isnan(value) else "+inf" if value > 0 else "-inf"}
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {str(key): encode(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported observed result type: {type(value).__name__}")


def emit(value):
    sys.__stdout__.write(json.dumps(value, allow_nan=False, separators=(",", ":")) + "\n")
    sys.__stdout__.flush()


def main():
    path = Path(sys.argv[1]).resolve()
    capture = io.StringIO()
    try:
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location("_morphproof_subject", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot load {path.name}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            # Compile these exact bytes. Timestamp/size-valid .pyc files can be
            # stale after rapid same-length repairs and would invalidate hashes.
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        emit({"ready": True})
    except BaseException as exc:
        emit({"ready": False, "error": {"kind": "load_error", "type": type(exc).__name__, "message": str(exc)}})
        return
    for line in sys.stdin:
        try:
            request = json.loads(line)
            values = decode(request["values"])
            binding_error = None
            # Resolve the declared API before entering the subject-exception
            # handler. Two absent functions must never look equivalent merely
            # because both getattr calls raise the same AttributeError.
            try:
                with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                    function = getattr(module, request["function"])
                if not callable(function):
                    raise TypeError(f"declared target {request['function']!r} is not callable")
                try:
                    signature = inspect.signature(function)
                except (ValueError, TypeError):
                    signature = None
                if signature is not None:
                    if not request.get("keyword"):
                        signature.bind(values)
                    else:
                        try:
                            signature.bind(**{request["keyword"]: values})
                        except TypeError as exc:
                            # Preserve the subject's real TypeError outcome so
                            # candidate-only API changes remain mismatches.
                            # The verifier separately invalidates an unbindable
                            # reference API instead of matching two failures.
                            binding_error = {"type": "TypeError", "message": str(exc)}
            except BaseException as exc:
                emit({"outcome": {"kind": "api_error", "type": type(exc).__name__, "message": str(exc)}, "lines": [], "arcs": []})
                capture.seek(0)
                capture.truncate(0)
                continue
            covered, arcs = set(), set()
            previous = {}

            def trace(frame, event, arg):
                if frame.f_code.co_filename == str(path):
                    if event == "line":
                        current = frame.f_lineno
                        covered.add(current)
                        key = id(frame)
                        if key in previous:
                            arcs.add((previous[key], current))
                        previous[key] = current
                    elif event == "return":
                        previous.pop(id(frame), None)
                    return trace
                return None

            started = time.perf_counter_ns()
            try:
                if request.get("trace"):
                    sys.settrace(trace)
                with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                    result = function(**{request["keyword"]: values}) if request.get("keyword") else function(values)
            except BaseException as exc:
                outcome = {"kind": "exception", "type": f"{type(exc).__module__}.{type(exc).__qualname__}", "message": str(exc)}
            else:
                try:
                    outcome = {"kind": "return", "type": type(result).__name__, "value": encode(result)}
                except BaseException as exc:
                    # Encoding is verifier work. Its failure must never become
                    # a matching exception allegedly raised by the subject.
                    outcome = {"kind": "observation_error", "type": type(exc).__name__,
                               "message": str(exc), "result_type": type(result).__name__}
            finally:
                sys.settrace(None)
            elapsed = time.perf_counter_ns() - started
            emit({"outcome": outcome, "lines": sorted(covered), "arcs": sorted(arcs), "elapsed_ns": elapsed,
                  "binding_error": binding_error})
            capture.seek(0)
            capture.truncate(0)
        except BaseException as exc:
            emit({"outcome": {"kind": "worker_error", "type": type(exc).__name__, "message": str(exc)}, "lines": [], "arcs": []})


if __name__ == "__main__":
    main()
