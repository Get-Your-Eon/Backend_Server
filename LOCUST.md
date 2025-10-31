# Locust: Quickstart for monitoring this service

This project includes a simple `locustfile.py` to monitor basic health and a couple of endpoints. Use Locust to run quick smoke/load checks while deploying.

Installation

- If you use Poetry (recommended):

```bash
poetry install
poetry add --dev locust
# or, after pulling changes:
poetry install --with dev
```

- If you prefer pip:

```bash
python -m pip install "locust>=2.0"
```

Running Locust (Web UI)

```bash
# Start locust and open the web UI at http://localhost:8089
poetry run locust -f locustfile.py --host https://your-deployed-host
```

Then open http://localhost:8089 in a browser and start a test (set number of users and spawn rate). Use small numbers for safety (e.g. 10 users, spawn rate 1).

Running Locust (headless, for short smoke test)

```bash
# Run 20 users for 2 minutes, headless
poetry run locust -f locustfile.py --host https://your-deployed-host -u 20 -r 2 --headless --run-time 2m
```

Configuration

- `LOCUST_HEALTH_PATH`: path used for the primary health check (defaults to `/health`).
- `LOCUST_EXTRA_PATHS`: comma-separated list of extra endpoints to check (default `/`).

Examples

```bash
# Check /health and /stations
LOCUST_HEALTH_PATH=/health LOCUST_EXTRA_PATHS="/ /stations" \
  poetry run locust -f locustfile.py --host https://your-deployed-host -u 5 -r 1 --headless --run-time 5m
```

Safety notes

- Avoid high load on production during critical deploy windows unless you have capacity and alarm hooks in place.
- Prefer short, headless checks for smoke testing and the Web UI if you need to observe realtime metrics.
- If you need more advanced behaviour (auth, dynamic payloads, or session flows), extend `locustfile.py` accordingly.

Support

If you want, I can also:
- Add a Dockerfile for running locust in a container
- Add a CI job that runs a short headless smoke test after deploy
