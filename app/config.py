from pydantic_settings import BaseSettings, SettingsConfigDict
import os

class Settings(BaseSettings):
    # .env 파일 로드, Docker에서는 환경 변수 직접 주입 가능
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --------------------------
    # 기본 프로젝트 설정
    # --------------------------
    PROJECT_NAME: str = "EV Charger Management API"
    API_VERSION: str = "1.0.0"

    # --------------------------
    # 데이터베이스 설정
    # --------------------------
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str = "postgres"
    DATABASE_HOST: str = "localhost"  # 로컬 기본값
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "Codyssey_Team_A"

    # 최종 DB URL (자동 구성)
    @property
    def DATABASE_URL(self) -> str:
        user = self.DATABASE_USER
        password = self.DATABASE_PASSWORD
        host = self.DATABASE_HOST
        port = self.DATABASE_PORT
        dbname = self.DATABASE_NAME
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"

    # --------------------------
    # Redis 설정
    # --------------------------
    REDIS_HOST: str = "localhost"  # 로컬 기본값
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    CACHE_EXPIRE_SECONDS: int = 300

    # --------------------------
    # Docker 환경이면 호스트 이름 변경
    # --------------------------
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if os.getenv("DOCKER_ENV", "false").lower() == "true":
            # Docker 컨테이너 내부 Redis 연결
            self.REDIS_HOST = os.getenv("REDIS_HOST", "redis")
            # Docker 컨테이너에서도 로컬 PostgreSQL 바라보기
            self.DATABASE_HOST = os.getenv("DATABASE_HOST", "host.docker.internal")

# Settings 인스턴스 생성
settings = Settings()
