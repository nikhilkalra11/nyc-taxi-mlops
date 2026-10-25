"""SageMaker SKLearn script-mode entry point."""

import argparse
import json
import os
from pathlib import Path

from taxi_mlops.training.core import run_training


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["fare", "demand"], required=True)
    args = parser.parse_args()
    task = args.task
    data_dir = Path(os.environ["SM_CHANNEL_TRAINING"])
    config_path = Path(__file__).resolve().parents[2] / "configs" / "training.yaml"
    # Config is copied into source_dir by scripts/launch_sagemaker.py.
    output = Path(os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    summary = run_training(config_path, data_dir, output, (task,))
    print(json.dumps(summary[task]["test"]))


if __name__ == "__main__":
    main()
