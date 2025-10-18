Goal

Apply a small patch to the repository https://github.com/Get-Your-Eon/Backend_Server to add a temporary endpoint that lets frontend API key holders delete station detail cache keys (keys starting with `station:detail:`). This is useful when Render Shell is not available.

Patch contents

File: app/main.py
- Adds an endpoint: POST /admin/cache-unlocked
- Protected by the existing frontend API key dependency (`frontend_api_key_required`).
- Accepts JSON payload: {"key": "station:detail:PCGCGH00140"}
- Only allows keys with prefix `station:detail:` and returns {"deleted": true, "key": "..."} on success.

How to apply (two options)

A) Apply via web editor (fast, no CLI needed)
1. Open the repository https://github.com/Get-Your-Eon/Backend_Server in GitHub.
2. Create a new branch: e.g., `feat/admin-cache-unlocked`.
3. Open `app/main.py` in the web editor and add the function shown in the patch at the end of router includes.
4. Commit changes to the new branch and create a Pull Request targeting `main`.
5. Once reviewed and merged, Render will auto-deploy (if auto-deploy enabled). If not, trigger a manual deploy in Render.

B) Apply via local clone + patch
1. Clone the repo locally (or add remote):
   ```bash
   git clone https://github.com/Get-Your-Eon/Backend_Server.git
   cd Backend_Server
   git checkout -b feat/admin-cache-unlocked
   ```
2. Apply the patch (if using this file):
   ```bash
   # from inside this repo clone
   git apply /path/to/add_admin_cache_unlocked.patch
   git add app/main.py
   git commit -m "feat(admin): add temporary /admin/cache-unlocked endpoint"
   git push origin feat/admin-cache-unlocked
   ```
3. Open GitHub and create a PR from `feat/admin-cache-unlocked` -> `main`.
4. Merge and deploy via Render (auto-deploy or manual deploy).

Testing after merge/deploy

1. Call the endpoint with frontend API key (escape `!` in zsh):
   ```bash
   curl -X POST https://<YOUR_BACKEND_URL>/admin/cache-unlocked \
     -H "Content-Type: application/json" \
     -H "x-api-key: <YOUR_FRONTEND_KEY>" \
     -d '{"key":"station:detail:PCGCGH00140"}'
   ```
2. Expect JSON: {"deleted": true, "key": "station:detail:PCGCGH00140"}
3. Then GET the station detail to verify values updated:
   ```bash
   curl -H "x-api-key: <YOUR_FRONTEND_KEY>" https://<YOUR_BACKEND_URL>/api/v1/stations/CG_CGH00140
   ```

Security note

This is a temporary, pragmatic fix only because you cannot access Render Shell. After the issue is resolved, consider removing this endpoint and/or rotating frontend API keys. For additional safety, you can restrict allowed keys or add extra validation before allowing deletion.

If you'd like, I can prepare a branch and open a PR against the target repo — I will need either permission to push or you can fork and I will create a PR from my fork. Let me know which workflow you prefer.
