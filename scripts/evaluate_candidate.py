"""Gate candidate models against incumbent using matching holdout data."""
import argparse
import json
from pathlib import Path

from taxi_mlops.lifecycle.gates import evaluate, read_metrics


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--incumbent', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--max-regression', type=float, default=0.02)
    parser.add_argument('--min-improvement', type=float, default=0.0)
    args = parser.parse_args()
    result = evaluate(read_metrics(args.candidate), read_metrics(args.incumbent),
                      max_regression=args.max_regression,
                      min_improvement=args.min_improvement)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    if not result['passed']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
