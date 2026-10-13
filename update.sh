#!/usr/bin/env bash
# update.sh: bring this PC to the latest main and rebuild. Run it after main has changed.
#
#   bash gouda.sh stop      (update.sh refuses while Gouda is running)
#   bash update.sh
#   bash gouda.sh start     (re-plug the IMU USB if no IMU data arrives: docs/sensor_supervision.md)
#
#   1. refuses while Gouda is running, and when tracked files of this repository have local changes (nothing is
#      overwritten; untracked files are left alone)
#   2. fetches main from origin, switches to the local main branch and fast-forwards it (never merges or rebases;
#      a local main that has diverged is reported)
#   3. runs setup.sh: installs what the new version needs, moves the drivers to the pinned commits when the pins have
#      changed, and builds
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$repo/../.." && pwd)"
stop() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }
pid_file="$workspace/gouda_data/run/gouda_core.pid"
if [[ -f "$pid_file" ]] && pgrep -g "$(cat "$pid_file")" >/dev/null 2>&1; then
  stop "Gouda is running. Stop it first: bash $repo/gouda.sh stop"
fi
cd "$repo"
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  git status --short --untracked-files=no | head -20
  stop "tracked files have local changes; commit or set them aside (git stash) first. Nothing was changed"
fi
before="$(git rev-parse --short HEAD)"; branch="$(git rev-parse --abbrev-ref HEAD)"
echo "== fetching main from $(git remote get-url origin)"
git fetch -q origin main:refs/remotes/origin/main   # explicit refspec: works with single-branch clones too
if [[ "$branch" != main ]]; then
  if git show-ref -q --verify refs/heads/main; then git switch -q main; else git switch -q -c main --track origin/main; fi
  echo "switched from $branch to main"
fi
git branch -q --set-upstream-to=origin/main main
git merge --ff-only -q origin/main || stop "the local main has commits that are not on origin/main; it was not changed (see: git log origin/main..main)"
after="$(git rev-parse --short HEAD)"
if [[ "$before" == "$after" ]]; then echo "already at $after"; else echo "$before -> $after"; git log --oneline "$before..$after" | head -20; fi
exec bash "$repo/setup.sh"
