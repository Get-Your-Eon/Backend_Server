# test_infra.py
import asyncio
import time
from datetime import datetime
import subprocess
import requests
from redis.asyncio import Redis

BASE_URL = "http://127.0.0.1:8000"

# ----------------------------
# 1. FastAPI 서버 헬스 체크
# ----------------------------
def test_fastapi_health():
    print("🌐 1. FastAPI 서버 헬스 체크 중...")
    try:
        resp = requests.get(f"{BASE_URL}/")
        print("응답:", resp.json())
    except Exception as e:
        print("FastAPI 서버 헬스 체크 실패:", e)

# ----------------------------
# 2. DB 테스트
# ----------------------------
def test_db():
    print("🗄️ 2. DB 연결 테스트 중...")
    try:
        resp = requests.get(f"{BASE_URL}/db-test")
        print("응답:", resp.json())
    except Exception as e:
        print("DB 테스트 실패:", e)

# ----------------------------
# 3. Redis 테스트
# ----------------------------
async def test_redis():
    print("🧩 3. Redis 연결 테스트 중...")
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
# 4. Alembic 마이그레이션 테스트
# ----------------------------
def test_alembic_upgrade():
    print("⚡ 4. Alembic 마이그레이션 실행 중...")
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
# 5. 전체 테스트 실행
# ----------------------------
def main():
    test_fastapi_health()
    test_db()
    asyncio.run(test_redis())
    test_alembic_upgrade()
    print("✅ 모든 인프라 테스트 완료!")

if __name__ == "__main__":
    main()
