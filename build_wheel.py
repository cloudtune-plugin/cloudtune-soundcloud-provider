"""Compatibility command: delegate all Wheel metadata and versioning to PEP 517."""
from pathlib import Path
import subprocess
import sys


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel"],
        cwd=Path(__file__).resolve().parent,
        check=True,
    )


if __name__ == "__main__":
    main()
