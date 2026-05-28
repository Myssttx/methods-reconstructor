"""Metric helpers for the eval harness."""

from __future__ import annotations


def resolution_rate(n_resolved: int, n_total: int) -> float:
    return n_resolved / n_total if n_total > 0 else 0.0


def in_range(value: float | None, lo: float, hi: float) -> bool:
    return value is not None and lo <= value <= hi
