"""Entry point for `fumble` CLI tool (dashboard)."""

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent


def main() -> None:
    os.chdir(_ROOT)
    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(Path(__file__).parent / "dashboard.py")]
    sys.exit(stcli.main())
