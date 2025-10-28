#!/usr/bin/env bash
set -euo pipefail

# Autosync origin -> render-origin safely with a temporary branch.
# Creates a stash if needed, merges origin/<branch> into render-origin/<branch>, pushes,
# creates tag f1 pointing at origin's latest if missing, sets upstream and pushDefault,
# then pops stash to restore local changes.

STASHED="no"
STASH_OUTPUT=$(git stash push -u -m "autosave before sync to render-origin $(date -u +%Y%m%dT%H%M%SZ)" 2>&1 || true)
if printf "%s" "$STASH_OUTPUT" | grep -q "No local changes to save"; then
  echo "No local changes to stash. Proceeding."
else
  echo "Stash created: $STASH_OUTPUT"
  STASHED="yes"
fi

ORIG_BR=$(git ls-remote --symref origin HEAD 2>/dev/null | awk "/ref:/ {print \$2}" | sed "s@refs/heads/@@")
REN_BR=$(git ls-remote --symref render-origin HEAD 2>/dev/null | awk "/ref:/ {print \$2}" | sed "s@refs/heads/@@")
ORIG_SHA=$(git rev-parse origin/$ORIG_BR)
REN_SHA=$(git rev-parse render-origin/$REN_BR)

echo "origin branch:$ORIG_BR ($ORIG_SHA)"
echo "render-origin branch:$REN_BR ($REN_SHA)"

BR_NAME="merge/sync-render-origin-$(date +%s)"

echo "Creating temporary branch $BR_NAME from render-origin/$REN_BR"
git checkout -b "$BR_NAME" "render-origin/$REN_BR"

echo "Merging origin/$ORIG_BR into $BR_NAME (no-fast-forward)..."
if ! git merge --no-ff --no-edit "origin/$ORIG_BR"; then
  echo "Merge reported conflicts. Listing unmerged files:"
  git status --porcelain || true
  git ls-files -u || true
  echo "Aborting merge and deleting temporary branch. Restoring stash if created."
  git merge --abort || true
  git checkout - || true
  git branch -D "$BR_NAME" || true
  if [ "$STASHED" = "yes" ]; then
    echo "Restoring stash (pop)..."
    git stash pop || echo "stash pop had conflicts or failed — please resolve manually"
  fi
  exit 2
fi

echo "Merge successful. Pushing merged branch to render-origin/$REN_BR..."
git push render-origin "$BR_NAME:$REN_BR"

echo "Push complete. Now creating tag 'f1' pointing to $ORIG_SHA if not present on remote..."
if git ls-remote --tags render-origin | grep -q "refs/tags/f1"; then
  echo "Remote tag 'f1' already exists on render-origin. Skipping tag creation."
  git ls-remote --tags render-origin | grep "refs/tags/f1" || true
else
  if git tag -l f1 | grep -q "^f1$"; then
    echo "Local tag 'f1' exists; moving it to $ORIG_SHA (force update local tag)."
    git tag -f -a f1 "$ORIG_SHA" -m "f1 tag pointing to $ORIG_SHA"
  else
    echo "Creating annotated tag 'f1' at $ORIG_SHA"
    git tag -a f1 "$ORIG_SHA" -m "f1 tag pointing to $ORIG_SHA"
  fi
  echo "Pushing tag 'f1' to render-origin..."
  git push render-origin refs/tags/f1
  echo "Tag pushed." 
fi

# set upstream for local main and default push
echo "Setting local branch 'main' upstream to render-origin/$REN_BR"
git branch --set-upstream-to=render-origin/$REN_BR main || true

echo "Setting git config remote.pushDefault to render-origin"
git config remote.pushDefault render-origin

# verification

echo "\n--- remotes ---"
git remote -v

echo "\n--- render-origin/$REN_BR SHA ---"
git rev-parse "render-origin/$REN_BR"

echo "\n--- tags pointing at origin SHA ($ORIG_SHA) ---"
git tag --points-at "$ORIG_SHA" || true

# restore stash if any
if [ "$STASHED" = "yes" ]; then
  echo "\nPopping stash to restore your local changes..."
  if git stash pop; then
    echo "Stash successfully applied and dropped."
  else
    echo "stash pop failed or resulted in conflicts — please run 'git stash list' and resolve manually." 
  fi
fi

echo "Done. Temporary branch $BR_NAME remains locally (delete if desired: git branch -D $BR_NAME)."
