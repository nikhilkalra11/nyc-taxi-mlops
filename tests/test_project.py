from pathlib import Path


def test_repository_structure():
    root = Path(__file__).resolve().parents[1]

    assert (root / "src" / "taxi_mlops").is_dir()
    assert (root / "infrastructure" / "environments" / "dev").is_dir()
    assert (root / "configs").is_dir()