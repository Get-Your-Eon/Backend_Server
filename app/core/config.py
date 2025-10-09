from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    # --------------------------
    # 기본 정보
    # --------------------------
    PROJECT_NAME: str = "EV Charger Management API"
    API_VERSION: str = "1.0.0"

    # --------------------------
    # 데이터베이스
    # --------------------------
    DATABASE_URL: str

    # --------------------------
    # 보안 관련
    # --------------------------
    SECRET_KEY: str = "YOUR_SUPER_SECRET_KEY_REPLACE_ME_NOW"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --------------------------
    # Redis 관련
    # --------------------------
    REDIS_HOST: str
    REDIS_PORT: int
    REDIS_PASSWORD: Optional[str] = None
    CACHE_EXPIRE_SECONDS: int = 300

    # --------------------------
    # 실행 환경
    # --------------------------
    ENVIRONMENT: str = "development"   # development / docker / production
    DOCKER_ENV: Optional[bool] = False

    @field_validator("DOCKER_ENV", mode="before")
    def parse_docker_env(cls, v):
        """DOCKER_ENV 값을 문자열에서 bool로 변환"""
        if isinstance(v, str):
            return v.lower() in ("1", "true", "yes")
        return v

    @model_validator(mode="after")
    def switch_redis_host(cls, values):
        """
        실행 환경에 따라 Redis 연결 정보를 자동 전환
        """
        env = values.ENVIRONMENT.lower()

        if env == "development":
            # 로컬 실행 시 (ex. uvicorn app.main:app --reload)
            values.REDIS_HOST = "localhost"
            values.REDIS_PORT = 6379
            values.REDIS_PASSWORD = None

        elif env == "docker":
            # Docker Compose 내부 실행 시
            values.REDIS_HOST = "ev_charger_redis"
            values.REDIS_PORT = 6379
            values.REDIS_PASSWORD = None

        elif env == "production":
            # Render 환경 (Render에서 제공하는 Redis 주소 사용)
            # .env의 설정값 그대로 사용
            pass

        return values

settings = Settings()
