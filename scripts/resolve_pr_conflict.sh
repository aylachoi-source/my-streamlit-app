#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash scripts/resolve_pr_conflict.sh
#   bash scripts/resolve_pr_conflict.sh <pr-branch>
#   bash scripts/resolve_pr_conflict.sh <pr-branch> --auto-ours-app

BRANCH="${1:-$(git branch --show-current)}"
AUTO_OURS_APP="${2:---auto-ours-app}"

if [[ -z "$BRANCH" ]]; then
  echo "Could not detect branch. Usage: $0 <pr-branch> [--auto-ours-app]"
  exit 1
fi

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
  # If app.py is conflicted, keep this PR branch's app.py.
  if git diff --name-only --diff-filter=U | rg -x "app.py" >/dev/null; then
    echo "Auto-resolving app.py with current branch version (ours)..."
    git checkout --ours app.py
    git add app.py
    # If only app.py was conflicted, this finalizes merge.
    if [[ -z "$(git diff --name-only --diff-filter=U)" ]]; then
      git commit -m "Resolve merge conflict: keep app.py from ${BRANCH}"
      echo "Conflict resolved with ours strategy for app.py. Push with:"
      echo "  git push origin $BRANCH"
      exit 0
    fi
  fi
fi

echo "Resolve remaining conflicts manually, then run:"
echo "  git add <files>"
echo "  git commit -m 'Resolve merge conflict with main'"
echo "  git push origin $BRANCH"
echo
echo "Tip: if app.py is the only conflict and you want to keep PR version, run:"
echo "  $0 $BRANCH --auto-ours-app"
exit 2
