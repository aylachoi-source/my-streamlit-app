#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <pr-branch> [--auto-ours-app]"
  exit 1
fi

BRANCH="$1"
AUTO_OURS_APP="${2:-}"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Working tree is not clean. Commit or stash changes first."
  exit 1
fi

if ! git remote get-url origin >/dev/null 2>&1; then
  echo "Remote 'origin' is not configured."
  exit 1
fi

git fetch origin

git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH"

set +e
git merge origin/main
MERGE_CODE=$?
set -e

if [[ $MERGE_CODE -eq 0 ]]; then
  echo "Merge completed without conflicts. Push with:"
  echo "  git push origin $BRANCH"
  exit 0
fi

echo "Merge conflict detected."

if [[ "$AUTO_OURS_APP" == "--auto-ours-app" ]]; then
  echo "Auto-resolving app.py with current branch version (ours)..."
  git checkout --ours app.py
  git add app.py
  git commit -m "Resolve merge conflict: keep app.py from ${BRANCH}"
  echo "Conflict resolved with ours strategy for app.py. Push with:"
  echo "  git push origin $BRANCH"
  exit 0
fi

echo "Resolve conflicts manually, then run:"
echo "  git add <files>"
echo "  git commit -m 'Resolve merge conflict with main'"
echo "  git push origin $BRANCH"
echo
echo "Tip: if app.py is the only conflict and you want to keep PR version, run:"
echo "  $0 $BRANCH --auto-ours-app"
exit 2
