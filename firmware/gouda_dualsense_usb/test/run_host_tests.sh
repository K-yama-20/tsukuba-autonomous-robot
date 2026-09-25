#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
build_dir="$(mktemp -d "${TMPDIR:-/tmp}/gouda-usb-fw-test.XXXXXX")"
trap 'rm -rf "$build_dir"' EXIT
g++ -std=c++17 -Wall -Wextra -Werror -I"$root/include" "$root/test/test_core.cpp" -o "$build_dir/test_core"
"$build_dir/test_core"
