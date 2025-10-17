#!/usr/bin/env bash
set -euo pipefail

# Simple deploy script: commit any local changes and push to render-origin main.
# Usage: ./scripts/deploy_render.sh "commit message"

MSG=${1:-"chore: deploy from script"}

echo "Checking git repository..."
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Not inside a git repository. Aborting."
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Uncommitted changes found. Adding and committing with message: '$MSG'"
  git add -A
  git commit -m "$MSG"
else
  echo "No uncommitted changes."
fi

echo "Pushing to remote 'render-origin' branch 'main'..."
git push render-origin main

echo "Push complete. Render will start a deploy based on the pushed commit."

echo "Next steps to check deploy status:"
echo "  - Open Render dashboard for your service and review the Deploy/Logs tab."
echo "  - If you have Render CLI installed, you can tail logs (replace <service> with your service name):"
echo "      render services logs <service> --tail"
echo "  - Or fetch recent events in the dashboard and paste logs here for analysis."

echo "If you want this script to automatically tail logs using the Render CLI, set RENDER_SERVICE_NAME env var and ensure 'render' CLI is installed."
if [ -n "${RENDER_SERVICE_NAME:-}" ]; then
  if command -v render >/dev/null 2>&1; then
    echo "Tailing logs for service: $RENDER_SERVICE_NAME"
    render services logs "$RENDER_SERVICE_NAME" --tail
  else
    echo "Render CLI not found. Install it from https://render.com/docs/cli if you want automatic log tailing."
  fi
fi

echo "Done. Paste deploy logs here and I'll analyze any errors."
