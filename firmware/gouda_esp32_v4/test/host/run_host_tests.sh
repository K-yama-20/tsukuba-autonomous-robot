#!/usr/bin/env bash
# Host test of the firmware core (TS-17/18/19 desk stub, TS-29). No hardware, no PlatformIO: g++ only.
# The configuration header is generated from design/generated/params/firmware_config.yaml + .trial.yaml (desk values).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fw="$(cd "$here/../.." && pwd)"
out="${TMPDIR:-/tmp}/gouda_esp32_v4_host"
mkdir -p "$out"
python3 "$fw/tools/gen_build_config.py" --trial --out "$out/build_config_trial.hpp"
g++ -std=c++17 -Wall -Wextra -O1 -I"$fw/include" -I"$out" "$here/test_core.cpp" -o "$out/test_core"
"$out/test_core"
