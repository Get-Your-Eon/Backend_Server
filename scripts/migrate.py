# scripts/migrate.py
import os
import subprocess
import sys
from datetime import datetime, timezone

def main():
    """자동 Alembic 마이그레이션 생성 및 적용 스크립트"""

    # 커밋 메시지 인자 확인
    if len(sys.argv) < 2:
        print("❌ 사용법: poetry run migrate '리비전 메시지'")
        sys.exit(1)

    message = sys.argv[1]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    print(f"🛠  [{timestamp}] Alembic 마이그레이션 시작...\n")

    try:
        # 1️⃣ 리비전 자동 생성
        subprocess.run(
            ["poetry", "run", "alembic", "revision", "--autogenerate", "-m", message],
            check=True,
        )

        # 2️⃣ DB에 업그레이드 적용
        subprocess.run(
            ["poetry", "run", "alembic", "upgrade", "head"],
            check=True,
        )

        print("\n✅ 마이그레이션 성공적으로 완료되었습니다!")
    except subprocess.CalledProcessError as e:
        print(f"\n❌ 마이그레이션 중 오류 발생: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
