import argparse
from pathlib import Path

from taxi_mlops.training.core import run_training


def main():
    parser = argparse.ArgumentParser(description="Train fare and demand models")
    parser.add_argument("--config", type=Path, default=Path("configs/training.yaml"))
    parser.add_argument("--data-root", type=Path, default=Path("data/features"))
    parser.add_argument("--output", type=Path, default=Path("artifacts/models"))
    parser.add_argument("--task", choices=["fare", "demand", "all"], default="all")
    args = parser.parse_args()
    tasks = ("fare", "demand") if args.task == "all" else (args.task,)
    summary = run_training(args.config, args.data_root, args.output, tasks)
    for task, result in summary.items():
        print(f"{task}: {result['winner']} validation RMSE={result['validation_rmse']:.4f} "
              f"test RMSE={result['test']['rmse']:.4f}")


if __name__ == "__main__":
    main()
