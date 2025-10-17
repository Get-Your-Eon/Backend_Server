from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv
import os

# --------------------------
# .env 파일 로드
# --------------------------
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
    # 외부 충전소 API 설정
    # --------------------------
    # 외부 충전소 API의 기본 URL (예: https://api.example.com)
    EXTERNAL_STATION_API_BASE_URL: Optional[str] = None
    # API Key (Render에서는 Secret으로 저장)
    EXTERNAL_STATION_API_KEY: Optional[str] = None
    # 인증 방식: 'header' 또는 'query'
    EXTERNAL_STATION_API_AUTH_TYPE: str = "header"
    # 인증 헤더명(예: Authorization, X-API-KEY) - header 방식일 때 사용
    EXTERNAL_STATION_API_KEY_HEADER_NAME: str = "Authorization"
    # 외부 API 호출 타임아웃(초)
    EXTERNAL_STATION_API_TIMEOUT_SECONDS: int = 10

    # --------------------------
    # 실행 환경
    # --------------------------
    # 기본을 Render/production 중심으로 설정합니다. 로컬 개발 시에는
    # Render Dashboard에 있는 환경변수를 로컬에 복제하지 않는 한 실행되지
    # 않도록 의도적으로 기본값을 강제하지 않습니다.
    ENVIRONMENT: str = "production"   # development / docker / production
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
        Docker 환경에서는 내부 서비스 이름으로 Redis를 지정합니다.
        Production(Render) 및 Development에서는 환경변수를 그대로 사용합니다.
        """
        env = values.ENVIRONMENT.lower()

        if env == "docker":
            # Docker Compose 실행 시
            values.REDIS_HOST = values.REDIS_HOST or "ev_charger_redis"
            values.REDIS_PORT = values.REDIS_PORT or 6379
            values.REDIS_PASSWORD = values.REDIS_PASSWORD or None

        elif env == "production":
            # Render 환경 — 환경변수에 설정된 값을 그대로 사용
            pass

        # development: do not override environment-provided values

        return values


# --------------------------
# 설정 인스턴스 생성
# --------------------------
settings = Settings()
