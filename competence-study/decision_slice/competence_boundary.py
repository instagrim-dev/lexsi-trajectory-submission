"""Evidence-backed, falsifiable applicability hypotheses for repair programs.

A hypothesis is an empirical conjunction over caller-supplied semantic features;
it is never a proof or authority to apply a repair. Independent qualification is
required even after a match. Do not include incidental identifiers as features.
"""
from __future__ import annotations

from itertools import combinations
import json
from pathlib import Path
from typing import Any


class CompetenceBoundary:
    def __init__(self) -> None:
        self.observations: dict[str, list[dict[str, Any]]] = {}
        self.retained: dict[str, list[dict[str, Any]]] = {}

    def observe(self, program: str, features: dict[str, Any], valid: bool, *, case: Any = None, expected: Any = None) -> None:
        """Record the outcome of an independently evaluated program instance."""
        if not program or not isinstance(valid, bool) or not features:
            raise ValueError("program, semantic features, and a boolean result are required")
        if not all(isinstance(k, str) and isinstance(v, (str, bool, int)) for k, v in features.items()):
            raise ValueError("features must have string names and scalar values")
        item = {"features": dict(sorted(features.items())), "valid": valid, "case": case, "expected": expected}
        json.dumps(item, allow_nan=False)
        observations = self.observations.setdefault(program, [])
        if item not in observations:
            observations.append(item)

    def hypothesis(self, program: str) -> dict[str, Any] | None:
        """Infer the least restrictive expressible conjunction consistent with observations.

        An empty dict means an unrefuted broad hypothesis; None means no positive
        evidence or no conjunction can distinguish observed successes and failures.
        Ties are broken lexicographically. Future tests can falsify any hypothesis.
        """
        observations = self.observations.get(program, [])
        positives = [o["features"] for o in observations if o["valid"]]
        negatives = [o["features"] for o in observations if not o["valid"]]
        if not positives:
            return None
        common = {k: v for k, v in positives[0].items() if all(k in p and p[k] == v for p in positives[1:])}
        keys = sorted(common)
        for length in range(len(keys) + 1):
            for selection in combinations(keys, length):
                if all(any(k in n and n[k] != common[k] for k in selection) for n in negatives):
                    return {k: common[k] for k in selection}
        return None

    def allows(self, program: str, features: dict[str, Any]) -> bool:
        hypothesis = self.hypothesis(program)
        return hypothesis is not None and all(k in features and features[k] == v for k, v in hypothesis.items())

    def retain_counterexample(self, program: str, requirement: str, case: Any, expected: Any) -> bool:
        """Retain a valid semantic example under its current requirement binding."""
        if not program or not requirement:
            raise ValueError("program and requirement binding are required")
        item = {"requirement": requirement, "case": case, "expected": expected}
        json.dumps(item, allow_nan=False)
        examples = self.retained.setdefault(program, [])
        if item in examples:
            return False
        examples.append(item)
        return True

    def counterexamples(self, program: str, current_requirement: str) -> list[dict[str, Any]]:
        return [dict(e) for e in self.retained.get(program, []) if e["requirement"] == current_requirement]

    def dump(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps({"version": 1, "observations": self.observations, "counterexamples": self.retained}, sort_keys=True, indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> "CompetenceBoundary":
        content = json.loads(Path(path).read_text())
        if content.get("version") != 1:
            raise ValueError("unsupported boundary store version")
        store = cls()
        for program, observations in content["observations"].items():
            for o in observations:
                store.observe(program, o["features"], o["valid"], case=o.get("case"), expected=o.get("expected"))
        for program, examples in content["counterexamples"].items():
            for e in examples:
                store.retain_counterexample(program, e["requirement"], e["case"], e["expected"])
        return store
