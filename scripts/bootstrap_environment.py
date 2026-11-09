"""Create a local virtual environment and install the Python project extras."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"


def virtualenv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def main() -> int:

    python = virtualenv_python()
    if not python.exists():
        print(f"Creating virtual environment at {VENV}")
        subprocess.run([sys.executable, "-m", "venv", str(VENV)], cwd=ROOT, check=True)
        python = virtualenv_python()

    commands = [
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        [str(python), "-m", "pip", "install", "-e", ".[dev]"],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)

    print("Setup complete. Run: python scripts/run_tests.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
