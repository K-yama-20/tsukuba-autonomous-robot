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
#
#   bash update.sh <branch> <commit>
#      brings this PC to one commit of another branch instead of main (the integration branch before it is in main).
#      Step 2 becomes: fetches <branch> from origin, checks that <commit> is on it, and checks it out detached
#      (no local branch is created or moved). Steps 1 and 3 are the same. Write the commit id into the work record.
set -eo pipefail
repo="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$(cd "$repo/../.." && pwd)"
stop() { printf '\nSTOPPED: %s\n' "$*" >&2; exit 1; }
if [[ $# -ne 0 && $# -ne 2 ]]; then stop "usage: bash update.sh            (latest main)
         bash update.sh <branch> <commit>   (one commit of another branch)"; fi
target_branch="${1:-}"; target_commit="${2:-}"
if [[ -n "$target_branch" ]]; then
  git check-ref-format --branch "$target_branch" >/dev/null 2>&1 || stop "not a branch name: $target_branch"
  [[ "$target_commit" =~ ^[0-9a-f]{7,40}$ ]] || stop "not a commit id (7 to 40 hex digits): $target_commit"
fi
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
if [[ -n "$target_branch" ]]; then
  echo "== fetching $target_branch from $(git remote get-url origin)"
  git fetch -q origin "$target_branch:refs/remotes/origin/$target_branch" || stop "could not fetch $target_branch from origin; nothing was changed"
  full="$(git rev-parse -q --verify "$target_commit^{commit}")" || stop "commit $target_commit was not found after the fetch; nothing was changed"
  git merge-base --is-ancestor "$full" "refs/remotes/origin/$target_branch" \
    || stop "commit $target_commit is not on origin/$target_branch; nothing was changed"
  git switch -q --detach "$full"
  after="$(git rev-parse --short HEAD)"
  if [[ "$before" == "$after" ]]; then echo "already at $after"; else echo "$before -> $after ($target_branch, detached; was on $branch)"; fi
  echo "commit: $full"
  exec bash "$repo/setup.sh"
fi
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
