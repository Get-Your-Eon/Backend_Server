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
    # Cache TTL in seconds for station SEARCH results. Use 300s (5 minutes)
    # per deployment request to balance freshness and load.
    CACHE_EXPIRE_SECONDS: int = 300
    # Cache TTL in seconds for station DETAIL results (charger specs/status).
    # Station-detail caches are kept longer (30 minutes) because they include
    # richer static/dynamic snapshots; dynamic charger statuses will still be
    # validated against the API policy in application logic.
    CACHE_DETAIL_EXPIRE_SECONDS: int = 1800
    # Number of decimal places to round coordinates for cache keys.
    # Higher precision (e.g., 8) keeps cache keys very local to exact coords.
    CACHE_COORD_ROUND_DECIMALS: int = 8

    # --------------------------
    # KEPCO API 설정 (기존 EXTERNAL_STATION_API 환경변수 활용)
    # --------------------------
    # KEPCO API Key는 기존 EXTERNAL_STATION_API_KEY 환경변수 사용
    @property
    def KEPCO_API_KEY(self) -> Optional[str]:
        return self.EXTERNAL_STATION_API_KEY
    
    # --------------------------
    # 외부 충전소 API 설정 (Legacy/KEPCO)
    # --------------------------
    # 외부 충전소 API의 기본 URL (예: https://bigdata.kepco.co.kr/openapi/v1/EVchargeManage.do)
    EXTERNAL_STATION_API_BASE_URL: Optional[str] = None
    # API Key (Render에서는 Secret으로 저장)
    EXTERNAL_STATION_API_KEY: Optional[str] = None
    # 인증 방식: 'header' 또는 'query'
    EXTERNAL_STATION_API_AUTH_TYPE: str = "header"
    # 인증 헤더명(예: Authorization, X-API-KEY) - header 방식일 때 사용
    EXTERNAL_STATION_API_KEY_HEADER_NAME: str = "Authorization"
    # 인증 쿼리 파라미터 이름(예: apiKey) - query 방식일 때 사용
    EXTERNAL_STATION_API_KEY_PARAM_NAME: str = "apiKey"
    # 응답 포맷 옵션 (json|xml)
    EXTERNAL_STATION_API_RETURN_TYPE: str = "json"
    # seed / batch 스크립트용 타임아웃(초)
    EXTERNAL_STATION_API_TIMEOUT_SEED_SECONDS: int = 30
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
    def switch_redis_host(self):
        """
        Docker 환경에서는 내부 서비스 이름으로 Redis를 지정합니다.
        Production(Render) 및 Development에서는 환경변수를 그대로 사용합니다.
        """
        env = (self.ENVIRONMENT or "").lower()

        if env == "docker":
            # Docker Compose 실행 시
            self.REDIS_HOST = self.REDIS_HOST or "ev_charger_redis"
            self.REDIS_PORT = self.REDIS_PORT or 6379
            self.REDIS_PASSWORD = self.REDIS_PASSWORD or None

        # production/development: do not override environment-provided values

        return self


# --------------------------
# 설정 인스턴스 생성
# --------------------------
settings = Settings()
