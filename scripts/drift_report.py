"""Offline feature drift report using population stability index (PSI).

Usage: python scripts/drift_report.py --baseline data/reference.csv --current data/current.csv --features trip_distance passenger_count --output artifacts/drift/report.json
Requires pandas and numpy (already used in the training project).
"""
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from taxi_mlops.observability.drift import psi


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
