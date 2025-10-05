# app/config.py 파일을 아래와 같이 수정하세요.

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field # pydantic.Field 임포트


class Settings(BaseSettings):
    # REDIS_HOST: str = Field(..., default="localhost")
    # ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ 여기가 오류였습니다!

    # 수정: Python 기본값 할당을 제거하고 Field() 내부에서 default로 전달합니다.
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    # REDIS_PASSWORD: str = Field(default=None) # 비밀번호가 있다면 추가

    # 프로젝트 설정을 .env 파일에서 로드하도록 지정
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

# 프로젝트 전역에서 사용할 설정 객체
settings = Settings()