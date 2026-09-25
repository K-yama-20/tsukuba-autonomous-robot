#!/usr/bin/env bash
set -eo pipefail
workspace="${1:?Usage: install_signal_runtime.sh WORKSPACE}"
venv="$workspace/.venvs/pedestrian_signal"
python="$venv/bin/python"
runtime_version='1.22.1'

if [[ -x "$python" ]] && "$python" -c \
  'import onnxruntime,sys; sys.exit(0 if onnxruntime.__version__ == "1.22.1" else 1)'; then
  exit 0
fi

mkdir -p "$workspace/.venvs"
if [[ ! -x "$python" ]]; then
  if ! python3 -m venv --system-site-packages "$venv"; then
    echo 'Could not create the pedestrian signal Python environment. Install python3-venv, or rerun setup without --skip-system.' >&2
    exit 1
  fi
fi

"$python" -m pip install --disable-pip-version-check --no-input --only-binary=:all: \
  "onnxruntime==$runtime_version"
"$python" -c \
  'import onnxruntime,sys; expected="1.22.1"; actual=onnxruntime.__version__; print("ONNX Runtime",actual); sys.exit(0 if actual == expected else 1)'
