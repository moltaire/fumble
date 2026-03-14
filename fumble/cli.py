"""Entry point for `fumblebee` CLI tool (pipeline)."""

import os
import runpy
from pathlib import Path

_ROOT = Path(__file__).parent.parent


def main() -> None:
    os.chdir(_ROOT)
    runpy.run_path(str(_ROOT / "main.py"), run_name="__main__")
