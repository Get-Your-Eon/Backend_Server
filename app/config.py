from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # 환경 변수를 .env 파일에서 로드합니다. (Docker 환경에서는 직접 주입됩니다.)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- 기본 프로젝트 설정 ---
    # 서버 충돌을 일으킨 PROJECT_NAME 속성을 추가합니다.
    PROJECT_NAME: str = "EV Charger Management API"

    # --- 데이터베이스 설정 (PostgreSQL + PostGIS) ---
    # 예시: postgresql+asyncpg://user:password@db_host:5432/db_name
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/ev_charger_db"
    API_VERSION: str = "1.0.0"
    # --- Redis 캐시 설정 ---
    # [수정]: Docker 컨테이너 환경에서 Redis 서비스 이름('redis' 또는 'my-redis')을 호스트로 사용하도록 변경
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379

    # 캐시 만료 시간 (초 단위). 예시로 300초(5분) 설정
    CACHE_EXPIRE_SECONDS: int = 300

settings = Settings()