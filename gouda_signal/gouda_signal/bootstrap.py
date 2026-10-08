"""Launch the GUI using the workspace's isolated ONNX Runtime environment."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def _runtime_python() -> Path:
    workspace = Path(os.environ.get("GOUDA_WORKSPACE", Path.home() / "gouda_ws")).expanduser()
    return workspace / ".venvs" / "pedestrian_signal" / "bin" / "python"


def main() -> int:
    runtime_python = _runtime_python()
    if not runtime_python.is_file() or not os.access(runtime_python, os.X_OK):
        print(
            "Pedestrian signal runtime is missing. Run `bash scripts/setup.sh` first; "
            f"expected Python at {runtime_python}.",
            file=sys.stderr,
        )
        return 2

    # Always exec the explicit venv path. A venv's Python often symlinks to
    # /usr/bin/python3, so comparing resolved executables would misidentify the
    # system interpreter as the venv and silently skip its site-packages.
    os.execv(
        str(runtime_python),
        [str(runtime_python), "-m", "gouda_signal.app", *sys.argv[1:]],
    )
    return 127  # pragma: no cover - execv replaces this process.


if __name__ == "__main__":
    raise SystemExit(main())
