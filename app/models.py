from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# 모든 모델이 상속받을 기본 클래스 정의
Base = declarative_base()

# ==============================================================================
# 1. station 테이블 (충전소 정보)
# ==============================================================================
class Station(Base):
    __tablename__ = "station"

    # ① 충전소 DB 내부 고유 ID, 기본 키 (Primary Key)
    station_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # ② 공공데이터 API에서 제공하는 충전소 고유 코드, 외부 식별자
    station_code = Column(String(50), unique=True, nullable=False, index=True)
    # ③ 충전소 이름 표시용
    station_name = Column(String(200), nullable=False)
    # ④ 충전소 상세 주소 정보
    address = Column(Text)
    # ⑤ 충전소 위경도 좌표 (Point, WGS84)
    location = Column(String(50))
    # ⑥ 충전소 운영사 정보
    provider = Column(String(100))
    # ⑦ 레코드 생성 시각 자동 기록
    created_at = Column(DateTime, default=func.now(), nullable=False)
    # ⑧ 레코드 최종 수정 시각 자동 기록
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship 정의: Station은 여러 개의 Charger를 가집니다.
    chargers = relationship("Charger", back_populates="station", cascade="all, delete-orphan")


# ==============================================================================
# 2. charger 테이블 (충전기 정보)
# ==============================================================================
class Charger(Base):
    __tablename__ = "charger"

    # ① 충전기 DB 내부 고유 ID, 기본 키
    charger_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # ② FK: 어떤 충전소에 속하는지 연결
    station_id = Column(Integer, ForeignKey("station.station_id"), nullable=False, index=True)
    # ③ 공공데이터 API에서 제공하는 충전기 고유 코드
    charger_code = Column(String(50))
    # ④ 충전기 종류 (DC콤보, AC완속 등)
    charger_type = Column(String(50))
    # ⑤ 충전기 출력 용량 (kW), 정밀도 5, 소수점 2자리
    output_kw = Column(Numeric(precision=5, scale=2))
    # ⑥ 커넥터 타입 정보 (타입별 호환성 확인용)
    connector_type = Column(String(50))
    # ⑦ 레코드 생성 시각 자동 기록
    created_at = Column(DateTime, default=func.now(), nullable=False)
    # ⑧ 레코드 최종 수정 시각 자동 기록
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship 정의: Charger는 하나의 Station에 속합니다.
    station = relationship("Station", back_populates="chargers")


# ==============================================================================
# 3. api_log 테이블 (API 호출 로그)
# ==============================================================================
class ApiLog(Base):
    __tablename__ = "api_log"

    # ① API 호출 로그 고유 ID, 기본 키
    log_id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # ② API 종류 (station, charger, status 등)
    api_type = Column(String(50), nullable=False)
    # ③ API 호출 시각 기록
    request_time = Column(DateTime, default=func.now(), nullable=False)
    # ④ API 응답 코드 기록 (HTTP 상태 등)
    response_code = Column(Integer)
    # ⑤ API 응답 메시지 기록 (오류 메시지, 상세 정보)
    response_msg = Column(Text)