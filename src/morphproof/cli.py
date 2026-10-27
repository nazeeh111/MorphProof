"""Small commands, explicit evidence, no provider credentials."""
import argparse
import json
import sys
from pathlib import Path
from .contracts import discover, load_contract


def main(argv=None):
    parser = argparse.ArgumentParser(prog="morphproof", description="Change the implementation. Record compatibility evidence.")
    parser.add_argument("--version", action="version", version="morphproof 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inspect", help="Inventory repository APIs, tests, docs and dependency manifests without execution")
    inventory.add_argument("repository", type=Path)
    inventory.add_argument("-o", "--output", type=Path)
    inspect = commands.add_parser("discover", help="Propose a reviewable contract from public signatures")
    inspect.add_argument("reference", type=Path)
    inspect.add_argument("-o", "--output", type=Path, required=True)
    trans = commands.add_parser("transform", help="Translate supported Python reductions to Rust, build and verify")
    trans.add_argument("reference", type=Path)
    trans.add_argument("--contract", type=Path, required=True)
    trans.add_argument("-o", "--output", type=Path, required=True)
    trans.add_argument("--no-build", action="store_true", help="Emit source only; no verification claim")
    trans.add_argument("--budget", type=int, default=128)
    trans.add_argument("--seed", type=int, default=0)
    verify = commands.add_parser("verify", help="Independently challenge a candidate")
    verify.add_argument("reference", type=Path)
    verify.add_argument("candidate", type=Path)
    verify.add_argument("--contract", type=Path, required=True)
    verify.add_argument("-o", "--output", type=Path, required=True)
    verify.add_argument("--budget", type=int, default=128)
    verify.add_argument("--seed", type=int, default=0)
    verify.add_argument("--strategy", choices=["adaptive", "random", "boundary", "uniform"], default="boundary", help="boundary is the evidence-backed default; adaptive is experimental")
    studio = commands.add_parser("studio", help="Render or serve local evidence")
    studio.add_argument("run", type=Path)
    studio.add_argument("--serve", action="store_true")
    studio.add_argument("--port", type=int, default=8765)
    prep = commands.add_parser("prepare-agent", help="Create an agent task and frozen acceptance snapshot")
    prep.add_argument("reference", type=Path)
    prep.add_argument("candidate", type=Path)
    prep.add_argument("--contract", type=Path, required=True)
    prep.add_argument("-o", "--output", type=Path, required=True)
    check = commands.add_parser("check-agent", help="Reject modified acceptance inputs")
    check.add_argument("task", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            from .inspection import inspect_repository
            result = json.dumps(inspect_repository(args.repository), indent=2) + "\n"
            if args.output:
                if args.output.exists():
                    raise ValueError("Output already exists; choose a new path")
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(result)
                print(args.output)
            else:
                print(result, end="")
        elif args.command == "discover":
            if args.output.exists():
                raise ValueError("Output already exists; choose a new path")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(discover(args.reference), indent=2) + "\n")
            print(str(args.output))
        elif args.command == "transform":
            from .transform import transform
            from .oracle import verify
            from .studio import render_studio
            contract = load_contract(args.contract)
            result = transform(args.reference, args.output, contract, build=not args.no_build)
            print(json.dumps(result, indent=2, default=str))
            if not args.no_build:
                candidate = Path(result.get("candidate", args.output / "candidate.py"))
                report = verify(args.reference, candidate, contract, args.output / "evidence", budget=args.budget, seed=args.seed)
                (args.output / "evidence" / "run.json").write_text(json.dumps({"reference_source":args.reference.read_text(), "rust_source":(args.output / "src" / "lib.rs").read_text()}, indent=2))
                render_studio(args.output / "evidence")
                print("Compatibility evidence: " + report["status"])
                return 0 if report["status"] == "compatible" else 1
        elif args.command == "verify":
            from .oracle import verify
            from .studio import render_studio
            result = verify(args.reference, args.candidate, load_contract(args.contract), args.output, budget=args.budget, seed=args.seed, strategy=args.strategy)
            render_studio(args.output)
            print(json.dumps({"status":result["status"], "totals":result["totals"], "report":str(args.output / "report.json")}, indent=2))
            return 0 if result["status"] == "compatible" else 1
        elif args.command == "studio":
            from .studio import render_studio, serve
            if args.serve:
                serve(args.run, port=args.port)
            else:
                print(render_studio(args.run))
        elif args.command == "prepare-agent":
            from .agents import prepare
            print(prepare(args.reference, args.contract, args.candidate, args.output))
        elif args.command == "check-agent":
            from .agents import check
            check(args.task)
            print("Acceptance snapshot unchanged")
        return 0
    except (ValueError, OSError, RuntimeError, SyntaxError) as exc:
        print("morphproof: " + str(exc), file=sys.stderr)
        return 2
