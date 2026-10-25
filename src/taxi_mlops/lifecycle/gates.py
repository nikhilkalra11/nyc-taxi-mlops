"""Deterministic quality gates for model promotion."""
from __future__ import annotations

import json
import math
from pathlib import Path


def read_metrics(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text())
    if not isinstance(obj, dict):
        raise TypeError('Metrics must be a JSON object')
    return obj


def evaluate(candidate: dict, incumbent: dict, *, max_regression: float = 0.02,
             min_improvement: float = 0.0) -> dict:
    """Compare RMSE for both models on the SAME evaluation dataset.

    Metrics shape: {"fare": {"rmse": ...}, "demand": {"rmse": ...}}.
    """
    if not 0 <= max_regression < 1 or min_improvement < 0:
        raise ValueError('Invalid thresholds')
    results = {}
    for task in ('fare', 'demand'):
        try:
            c = float(candidate[task]['rmse'])
            p = float(incumbent[task]['rmse'])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError(f'Missing/invalid {task}.rmse') from exc
        if not all(math.isfinite(x) and x > 0 for x in (c, p)):
            raise ValueError(f'{task}.rmse must be finite and positive')
        change = (p - c) / p
        passed = change >= min_improvement and c <= p * (1 + max_regression)
        results[task] = {'candidate_rmse': c, 'incumbent_rmse': p,
                         'relative_improvement': change, 'passed': passed}
    return {'passed': all(r['passed'] for r in results.values()), 'tasks': results}
