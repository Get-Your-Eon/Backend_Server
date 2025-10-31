# test_infra.py
import asyncio
import time
from datetime import datetime
import subprocess
import requests
from redis.asyncio import Redis

BASE_URL = "http://127.0.0.1:8000"

# ----------------------------
# 1. FastAPI health check
# ----------------------------
def test_fastapi_health():
    print("1. Checking FastAPI health...")
    try:
        resp = requests.get(f"{BASE_URL}/")
        print("Response:", resp.json())
    except Exception as e:
        print("FastAPI health check failed:", e)

# ----------------------------
# 2. Database test
# ----------------------------
def test_db():
    print("2. Testing database connectivity...")
    try:
        resp = requests.get(f"{BASE_URL}/db-test")
        print("Response:", resp.json())
    except Exception as e:
        print("Database test failed:", e)

# ----------------------------
# 3. Redis test
# ----------------------------
async def test_redis():
    print("3. Testing Redis connection...")
    r = Redis()
    test_key = "infra:test:key"
    test_value = {"status": "ok", "timestamp": datetime.now().isoformat()}

    try:
        await r.set(test_key, str(test_value), ex=10)
        val = await r.get(test_key)
        print("Redis 값 확인:", val.decode() if val else None)
    except Exception as e:
        print("Redis 테스트 실패:", e)
    finally:
        await r.close()

# ----------------------------
# 4. Alembic migration test
# ----------------------------
def test_alembic_upgrade():
    print("4. Running Alembic upgrade to head...")
    try:
        result = subprocess.run(
            ["poetry", "run", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
        )
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print("Alembic 마이그레이션 실패:", e.stderr)

# ----------------------------
# 5. Run all checks
# ----------------------------
def main():
    test_fastapi_health()
    test_db()
    asyncio.run(test_redis())
    test_alembic_upgrade()
    print("All infra tests completed")

if __name__ == "__main__":
    main()
