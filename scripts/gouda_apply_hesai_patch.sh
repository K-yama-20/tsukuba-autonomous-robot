set -e
workspace="${GOUDA_WORKSPACE:-$HOME/gouda_ws}"
driver="$workspace/src/HesaiLidar_ROS_2.0"
patch="$workspace/src/tsukuba-autonomous-robot/patches/hesai-replay-timestamps.patch"
test "$(git -C "$driver" rev-parse HEAD)" = e7e112f0809f0eed5e3c81c55a1a0376474db234
if git -C "$driver" apply --reverse --check "$patch" 2>/dev/null; then
  echo 'Hesai replay patch already applied'
else
  git -C "$driver" apply --check "$patch"
  git -C "$driver" apply "$patch"
fi
