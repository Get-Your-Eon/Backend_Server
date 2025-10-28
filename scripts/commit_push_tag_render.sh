#!/usr/bin/env bash
set -euo pipefail

echo "Current branch: $(git symbolic-ref --short HEAD)"
echo "Git status (porcelain):"
git status --porcelain || true

echo "\nStaging all changes (including untracked)..."
git add -A

if git diff --cached --quiet; then
  echo "No staged changes to commit. Exiting with code 0."
  exit 0
else
  echo "Committing with message: chore(post-merge): commit remaining local changes"
  git commit -m "chore(post-merge): commit remaining local changes"
fi

NEW_SHA_SHORT=$(git rev-parse --verify --short HEAD)
NEW_SHA_FULL=$(git rev-parse --verify HEAD)
echo "Committed: $NEW_SHA_SHORT ($NEW_SHA_FULL)"

echo "Pushing this commit to render-origin/main..."
# Push current HEAD to render-origin main
git push render-origin HEAD:main

echo "Pushing succeeded. Now updating tag f1 to point at $NEW_SHA_FULL and pushing (force)..."
# create/update annotated tag f1 pointing to new commit
if git tag -l f1 | grep -q "^f1$"; then
  git tag -f -a f1 "$NEW_SHA_FULL" -m "f1 tag pointing to $NEW_SHA_FULL"
else
  git tag -a f1 "$NEW_SHA_FULL" -m "f1 tag pointing to $NEW_SHA_FULL"
fi

# push tag force-update
git push --force render-origin refs/tags/f1

echo "Tag f1 now points to: $(git rev-parse refs/tags/f1^{})"

echo "Verification: render-origin/main -> $(git ls-remote render-origin refs/heads/main | awk '{print $1}')"
echo "render-origin tags (f1):"
git ls-remote --tags render-origin | grep "refs/tags/f1" || true

echo "Done."
