from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ENVIRONMENT 확인 후 해당 .env 로드
ENV = os.getenv("ENVIRONMENT", "development").lower()
env_file = ".env.production" if ENV == "production" else ".env.development"
load_dotenv(dotenv_path=BASE_DIR / env_file, override=True)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    PROJECT_NAME: str = "EV Charger Management API"
    API_VERSION: str = "1.0.0"

    DATABASE_URL: str

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: Optional[str] = None
    CACHE_EXPIRE_SECONDS: int = 300

    ENVIRONMENT: str = "development"   # development / docker / production
    DOCKER_ENV: Optional[bool] = False

    @field_validator("DOCKER_ENV", mode="before")
    def parse_docker_env(cls, v):
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return v

    @model_validator(mode="after")
    def switch_hosts(cls, values):
        env = values.ENVIRONMENT.lower()
        # 로컬 개발
        if env == "development":
            values.REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
            values.REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
            values.REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
        # Docker Compose 내부 실행
        elif env == "docker":
            values.REDIS_HOST = os.getenv("REDIS_HOST", "ev_charger_redis")
            values.REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
            values.REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)
            # Docker 내부에서 DB는 호스트 머신 바라보기
            if not os.getenv("DATABASE_URL"):
                db_host = os.getenv("DATABASE_HOST", "host.docker.internal")
                values.DATABASE_URL = f"postgresql://postgres:postgres@{db_host}:5432/Codyssey_Team_A"
        # Render / Production 환경
        elif env == "production":
            # .env.production 값 그대로 사용
            pass
        return values

settings = Settings()
