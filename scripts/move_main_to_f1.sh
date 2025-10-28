#!/usr/bin/env bash
set -euo pipefail

# Move local main to tag f1 and push to render-origin. Stash any uncommitted changes and restore after.

STASHED="no"
if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree not clean — stashing changes"
  git stash push -u -m "autosave before moving main to f1 $(date -u +%Y%m%dT%H%M%SZ)"
  STASHED="yes"
else
  echo "Working tree clean."
fi

# Ensure tag f1 exists (local or fetch)
if ! git rev-parse --verify --quiet refs/tags/f1; then
  echo "Tag f1 not found locally — fetching from render-origin"
  git fetch render-origin tag f1 || true
fi
if ! git rev-parse --verify --quiet refs/tags/f1; then
  echo "ERROR: tag f1 not found. Aborting."; exit 1
fi

F1_SHA=$(git rev-parse refs/tags/f1)
F1_SHORT=$(git rev-parse --short refs/tags/f1)
echo "f1 -> $F1_SHORT ($F1_SHA)"

# Checkout or create main
if git show-ref --verify --quiet refs/heads/main; then
  echo "Checking out existing local main"
  git checkout main
else
  echo "Creating local main tracking render-origin/main"
  git checkout -b main render-origin/main
fi

# Reset main to f1
echo "Resetting local main to f1 ($F1_SHORT)"
git reset --hard "$F1_SHA"

# Push main to render-origin
echo "Pushing local main to render-origin/main"
# If remote already at same SHA, push will be no-op
REMOTE_MAIN_SHA=$(git ls-remote render-origin refs/heads/main | awk '{print $1}')
if [ "$REMOTE_MAIN_SHA" = "$F1_SHA" ]; then
  echo "render-origin/main already at f1. Running normal push (no-op)."
  git push render-origin main || true
else
  echo "Pushing main to render-origin"
  git push render-origin main
fi

# Ensure upstream
git branch --set-upstream-to=render-origin/main main || true

echo "Verification: local main -> $(git rev-parse --short main)"
echo "render-origin/main -> $(git ls-remote render-origin refs/heads/main | awk '{print $1}')"

echo "Tags on render-origin pointing at main SHA:"
git ls-remote --tags render-origin | grep $(git rev-parse main) || true

# Restore stash if any
if [ "$STASHED" = "yes" ]; then
  echo "Popping stash to restore prior working tree"
  if git stash pop; then
    echo "Stash applied."
  else
    echo "stash pop failed or produced conflicts — please resolve manually."
  fi
fi

echo "Done. main now matches f1 ($F1_SHORT)."
