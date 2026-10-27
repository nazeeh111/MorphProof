"""Replay saved counterexamples against a repaired candidate.
Usage: python replay.py reference.py candidate.py
Requires an installed morphproof package.
"""
from pathlib import Path
import sys
from morphproof.oracle import replay_cases

if __name__ == "__main__":
    raise SystemExit(0 if replay_cases(Path(sys.argv[1]), Path(sys.argv[2]), Path(__file__).with_name("counterexamples.json"), Path(__file__).with_name("contract.snapshot.json")) else 1)
