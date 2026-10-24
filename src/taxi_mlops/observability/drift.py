"""Offline feature drift report using population stability index (PSI).

Usage: python scripts/drift_report.py --baseline data/reference.csv --current data/current.csv --features trip_distance passenger_count --output artifacts/drift/report.json
Requires pandas and numpy (already used in the training project).
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd


def psi(reference: pd.Series, current: pd.Series, bins: int = 10) -> float:
    ref = pd.to_numeric(reference, errors="coerce").dropna().to_numpy(dtype=float)
    cur = pd.to_numeric(current, errors="coerce").dropna().to_numpy(dtype=float)
    ref, cur = ref[np.isfinite(ref)], cur[np.isfinite(cur)]
    if len(ref) < 20 or len(cur) < 20:
        raise ValueError("Need at least 20 finite observations in each sample")
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        raise ValueError("Reference feature has insufficient distinct values")
    edges[0], edges[-1] = -np.inf, np.inf
    a = np.histogram(ref, bins=edges)[0].astype(float)
    b = np.histogram(cur, bins=edges)[0].astype(float)
    a = np.maximum(a / a.sum(), 1e-6)
    b = np.maximum(b / b.sum(), 1e-6)
    return float(np.sum((b - a) * np.log(b / a)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--features", nargs="+", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    baseline, current = pd.read_csv(args.baseline), pd.read_csv(args.current)
    results = {}
    for feature in args.features:
        if feature not in baseline or feature not in current:
            raise KeyError(f"Missing feature: {feature}")
        try:
            value = psi(baseline[feature], current[feature])
            results[feature] = {"psi": round(value, 5), "flag": value >= 0.2}
        except ValueError as exc:
            results[feature] = {"error": str(exc)}
    output = {"timestamp_utc": datetime.now(UTC).isoformat(), "features": results,
              "note": "PSI is a distribution-change signal, not an accuracy metric."}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
