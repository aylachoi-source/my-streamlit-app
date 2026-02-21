#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <pr-branch>"
  exit 1
fi

BRANCH="$1"

# ensure clean working tree
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

if [[ $MERGE_CODE -ne 0 ]]; then
  echo "Merge conflict detected. Resolve conflicts, then run:"
  echo "  git add <files>"
  echo "  git commit -m 'Resolve merge conflict with main'"
  echo "  git push origin $BRANCH"
  exit 2
fi

echo "Merge completed without conflicts. Push with:"
echo "  git push origin $BRANCH"
