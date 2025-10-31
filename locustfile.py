from locust import HttpUser, task, between
import os

# Configurable endpoints via environment variables:
# LOCUST_HEALTH_PATH (default: /health)
# LOCUST_EXTRA_PATHS (comma-separated list, default: /)

HEALTH_PATH = os.getenv("LOCUST_HEALTH_PATH", "/health")
EXTRA_PATHS = os.getenv("LOCUST_EXTRA_PATHS", "/")
EXTRA_PATHS = [p.strip() for p in EXTRA_PATHS.split(",") if p.strip()]

class QuickHealthUser(HttpUser):
    wait_time = between(1, 3)

    @task(5)
    def health(self):
        self.client.get(HEALTH_PATH, name=f"GET {HEALTH_PATH}")

    @task(2)
    def extra_paths(self):
        for p in EXTRA_PATHS:
            self.client.get(p, name=f"GET {p}")

    # Simple example of a POST (uncomment and adapt if needed)
    # @task(1)
    # def post_example(self):
    #     self.client.post("/some-endpoint", json={"ping": "pong"}, name="POST /some-endpoint")
