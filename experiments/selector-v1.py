"""Reproducible numeric challenges and reference-only adaptive selection.

The selector is deliberately transparent: static hazards seed priorities, input
feature novelty drives exploration, and observed reference coverage/outcomes
update family rewards. No candidate outputs influence selection.
"""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import dataclass
import math
import random
import sys


@dataclass
class Challenge:
    values: list[float]
    family: str


def analyze(source: str) -> dict:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"constants": [], "hazards": []}
    constants, hazards = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            try:
                value = float(node.value)
                if math.isfinite(value):
                    constants.add(value)
            except OverflowError:
                pass
        if isinstance(node, (ast.For, ast.While)):
            hazards.add("reduction")
        if isinstance(node, (ast.Div, ast.FloorDiv, ast.Mod)):
            hazards.add("division")
        if isinstance(node, (ast.Compare, ast.If, ast.IfExp)):
            hazards.add("branch")
        if isinstance(node, ast.Subscript):
            hazards.add("index")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {"sum", "min", "max", "sorted", "abs"}:
            hazards.add(node.func.id)
    return {"constants": sorted(constants)[:32], "hazards": sorted(hazards)}


def features(values: list[float], constants=()) -> frozenset[str]:
    length = len(values)
    out = {"len:" + ("0" if not length else "1" if length == 1 else "2" if length == 2 else "short" if length < 8 else "long")}
    if length and all(value == values[0] for value in values):
        out.add("repeated")
    finite = [value for value in values if math.isfinite(value)]
    for value in values:
        if math.isnan(value):
            out.add("nan")
        elif math.isinf(value):
            out.add("+inf" if value > 0 else "-inf")
        elif value == 0:
            out.add("-zero" if math.copysign(1, value) < 0 else "+zero")
        else:
            out.add("positive" if value > 0 else "negative")
            out.add("tiny" if abs(value) < 1e-200 else "large" if abs(value) > 1e150 else "ordinary")
        for constant in constants:
            if math.isfinite(value) and value == constant:
                out.add(f"constant:{constant!r}")
    if finite and min(finite) < 0 < max(finite):
        out.add("mixed-sign")
    if finite and max(abs(value) for value in finite) > 1e15 and any(0 < abs(value) < 10 for value in finite):
        out.add("cancellation")
    return frozenset(out)


def boundaries(max_length: int, constants=(), allow_nonfinite=True) -> list[Challenge]:
    raw = [([], "empty"), ([0.0], "zero"), ([-0.0], "zero"), ([1.0], "singleton"), ([-1.0], "singleton"),
           ([1.0, -1.0], "sign"), ([1e16, 1.0, -1e16], "cancellation"),
           ([1e308, 1e308], "overflow"), ([1e-300, -1e-300], "underflow"),
           ([0.0, 0.0], "zero"), ([2.0, 2.0], "repeated"),
           ([-2.0, 3.0, -4.0], "sign"), ([1.0, 2.0, 3.0], "ordinary")]
    if allow_nonfinite:
        raw += [([math.nan], "nan"), ([math.inf], "infinity"), ([-math.inf], "infinity"),
                ([math.inf, -math.inf], "infinity"), ([0.0, math.nan], "nan"), ([math.nan, 1.0], "nan")]
    for constant in constants:
        raw.extend([([constant], "constant"), ([math.nextafter(constant, -math.inf)], "threshold"),
                    ([math.nextafter(constant, math.inf)], "threshold"), ([constant, -constant], "constant")])
    raw.extend([([1.0] * min(max_length, size), "length") for size in [3, 7, 8, 31, 32, max_length]])
    return [Challenge(values, family) for values, family in raw if len(values) <= max_length and (allow_nonfinite or all(math.isfinite(value) for value in values))]


class Selector:
    """Budget counts tested candidates; pool scoring performs no subject execution."""
    def __init__(self, source: str, max_length=256, seed=0, strategy="adaptive", allow_nonfinite=True):
        if strategy not in {"adaptive", "random", "uniform", "boundary"}:
            raise ValueError(f"unknown strategy: {strategy}")
        self.strategy, self.max_length = strategy, max_length
        self.allow_nonfinite = allow_nonfinite
        self.rng = random.Random(seed)
        self.analysis = analyze(source)
        self.pool = boundaries(max_length, self.analysis["constants"], allow_nonfinite)
        self.base = list(self.pool)
        self.seen_features, self.seen_lines, self.seen_arcs, self.seen_outcomes = set(), set(), set(), set()
        self.counts, self.rewards = Counter(), Counter()
        self.index = 0
        for _ in range(384):
            self.pool.append(self._random_challenge())
        self.pool_features = {id(item): features(item.values, self.analysis["constants"]) for item in self.pool}

    def _random_challenge(self):
        length = self.rng.choice([0, 1, 2, 3, 8, 16, min(64, self.max_length), self.max_length])
        length = min(length, self.max_length)
        family = self.rng.choice(["ordinary", "sign", "zero", "repeated", "cancellation", "scale", "threshold"])
        if family == "ordinary":
            values = [self.rng.uniform(-100, 100) for _ in range(length)]
        elif family == "sign":
            values = [float(self.rng.randint(-10, 10)) for _ in range(length)]
        elif family == "zero":
            values = [self.rng.choice([0.0, -0.0, 1.0, -1.0]) for _ in range(length)]
        elif family == "repeated":
            values = [self.rng.uniform(-10, 10)] * length
        elif family == "cancellation":
            values = [self.rng.choice([1e16, -1e16, 1.0, -1.0, 0.0]) for _ in range(length)]
        elif family == "scale":
            values = [self.rng.choice([-1.0, 1.0]) * 10.0 ** self.rng.randint(-308, 308) for _ in range(length)]
        else:
            constants = self.analysis["constants"] or [0.0, 1.0]
            values = [math.nextafter(self.rng.choice(constants), self.rng.choice([-math.inf, math.inf])) for _ in range(length)]
            if not self.allow_nonfinite:
                values = [value if math.isfinite(value) else math.copysign(sys.float_info.max, value) for value in values]
        if self.allow_nonfinite and length and self.rng.random() < .07:
            values[self.rng.randrange(length)] = self.rng.choice([math.nan, math.inf, -math.inf])
            family = "nonfinite"
        return Challenge(values, family)

    def next(self) -> Challenge:
        if self.strategy == "uniform":
            length = self.rng.randint(0, self.max_length)
            chosen = Challenge([self.rng.uniform(-100, 100) for _ in range(length)], "uniform")
        elif self.strategy == "random":
            chosen = self._random_challenge()
        elif self.strategy == "boundary":
            chosen = self.base[self.index % len(self.base)]
        else:
            if not self.pool:
                self.pool.extend(self._random_challenge() for _ in range(128))
                self.pool_features = {id(item): features(item.values, self.analysis["constants"]) for item in self.pool}
            hazards = set(self.analysis["hazards"])
            def score(item):
                feat = self.pool_features[id(item)]
                novelty = len(feat - self.seen_features)
                family_count = self.counts[item.family]
                reward = self.rewards[item.family] / (family_count + 1)
                risk = 0.0
                if "division" in hazards and item.family in {"empty", "zero", "underflow"}:
                    risk += 1.5
                if "reduction" in hazards and item.family in {"cancellation", "overflow", "length"}:
                    risk += 1.0
                if "branch" in hazards and item.family in {"threshold", "constant", "nan"}:
                    risk += 1.0
                if "index" in hazards and item.family in {"empty", "singleton", "length"}:
                    risk += 1.0
                # Reference-only novelty and bandit feedback, with diminishing exploitation.
                return 3 * novelty + (risk + reward + 1) / (family_count + 1) + 1 / (len(item.values) + 1)
            best = max(range(len(self.pool)), key=lambda i: score(self.pool[i]))
            chosen = self.pool.pop(best)
            self.pool_features.pop(id(chosen))
        self.index += 1
        self.counts[chosen.family] += 1
        self.seen_features.update(features(chosen.values, self.analysis["constants"]))
        return chosen

    def observe(self, challenge: Challenge, observation: dict):
        lines = set(observation.get("lines", []))
        arcs = {tuple(arc) for arc in observation.get("arcs", [])}
        outcome = observation.get("outcome", {})
        # Numeric return values are intentionally not each treated as novel.
        signature = (outcome.get("kind"), outcome.get("type"), outcome.get("message"),
                     str(outcome.get("value")) if isinstance(outcome.get("value"), dict) else None)
        reward = len(lines - self.seen_lines) + len(arcs - self.seen_arcs) + int(signature not in self.seen_outcomes)
        self.rewards[challenge.family] += reward
        self.seen_lines.update(lines)
        self.seen_arcs.update(arcs)
        self.seen_outcomes.add(signature)

    def metrics(self):
        return {"feedback": "reference-only", "families": dict(sorted(self.counts.items())),
                "reference_lines": sorted(self.seen_lines), "reference_arcs": [list(arc) for arc in sorted(self.seen_arcs)],
                "input_features": sorted(self.seen_features), "structural_analysis": self.analysis}
