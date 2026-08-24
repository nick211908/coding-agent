from __future__ import annotations

import subprocess
import sys


def main() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "main", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    if "Usage:" not in result.stdout:
        raise SystemExit("CLI help output did not contain expected usage text")


if __name__ == "__main__":
    main()
