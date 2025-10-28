#!/usr/bin/env bash
set -euo pipefail

# Autosync origin -> render-origin safely, preferring origin when conflicts occur.
# Creates a stash if needed, merges origin/<branch> into render-origin/<branch> using -X theirs,
# pushes, force-updates tag f1 to origin latest, sets upstream and pushDefault, then pops stash.

STASHED="no"
STASH_OUTPUT=$(git stash push -u -m "autosave before sync to render-origin $(date -u +%Y%m%dT%H%M%SZ)" 2>&1 || true)
if printf "%s" "$STASH_OUTPUT" | grep -q "No local changes to save"; then
  echo "No local changes to stash."
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

# Merge preferring origin (theirs)
echo "Merging origin/$ORIG_BR into $BR_NAME with -X theirs..."
if git merge -s recursive -X theirs "origin/$ORIG_BR" -m "Merge origin/$ORIG_BR into render-origin/$REN_BR preferring origin (theirs)"; then
  echo "Merge completed without conflicts."
else
  echo "Merge had conflicts; attempting automatic conflict resolution by taking origin/theirs for all unmerged files..."
  # For each unmerged file, checkout theirs and stage
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    echo "Resolving $f by taking theirs..."
    git checkout --theirs -- "$f" || true
    git add -- "$f" || true
  done < <(git diff --name-only --diff-filter=U)
  # Commit the resolved files
  git commit -m "Resolve merge conflicts by preferring origin (theirs)" || true
fi

# Push merged result to render-origin
echo "Pushing merged branch to render-origin/$REN_BR..."
git push render-origin "$BR_NAME:$REN_BR"

echo "Preparing tag f1 at $ORIG_SHA (origin latest). Remote f1, if exists, will be force-updated."
if git ls-remote --tags render-origin | grep -q "refs/tags/f1"; then
  echo "Remote tag f1 exists on render-origin; force-updating to $ORIG_SHA."
  git tag -f -a f1 "$ORIG_SHA" -m "f1 tag pointing to $ORIG_SHA"
  git push --force render-origin refs/tags/f1
else
  echo "Creating annotated tag f1 at $ORIG_SHA and pushing."
  git tag -a f1 "$ORIG_SHA" -m "f1 tag pointing to $ORIG_SHA"
  git push render-origin refs/tags/f1
fi

# Set local main upstream and default push
echo "Setting local branch 'main' upstream to render-origin/$REN_BR"
git branch --set-upstream-to=render-origin/$REN_BR main || true

echo "Setting remote.pushDefault to render-origin"
git config remote.pushDefault render-origin

# Verification

echo "\n--- remotes ---"
git remote -v

echo "\n--- render-origin/$REN_BR SHA(after push) ---"
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

echo "Done. Temporary branch $BR_NAME remains locally; delete with: git branch -D $BR_NAME"
