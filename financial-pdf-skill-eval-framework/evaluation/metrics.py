"""Lightweight accuracy aggregation helpers (the heavy lifting lives in the Skill's evaluate_with_ground_truth.py)."""
from __future__ import annotations

from typing import Iterable


def average(values: Iterable[float]) -> float:
    vs = [v for v in values if v is not None]
    if not vs:
        return 0.0
    return sum(vs) / len(vs)
