"""Container-local deadline survives a worker crash or lost Docker client."""

from pathlib import Path
import subprocess
import sys


def main() -> int:
    try:
        child = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("entry.py")), sys.argv[1]],
            timeout=max(0.1, float(sys.argv[2])),
            check=False,
        )
        return child.returncode
    except subprocess.TimeoutExpired:
        print("Game engine execution deadline exceeded", file=sys.stderr)
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
