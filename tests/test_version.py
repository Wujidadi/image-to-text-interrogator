import tomllib
from pathlib import Path

import image_interrogator


def test_version_matches_pyproject():
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as f:
        assert image_interrogator.__version__ == tomllib.load(f)["project"]["version"]
