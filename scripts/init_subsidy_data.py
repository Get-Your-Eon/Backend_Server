import os
import sys
import asyncio
import re
from typing import List, Tuple

# ⚠️ [수정된 부분]: 스크립트가 'app' 디렉토리 밖에 있으므로,
# 'app' 모듈을 찾을 수 있도록 프로젝트 루트 디렉토리를 검색 경로에 추가합니다.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# SQLAlchemy 비동기 컴포넌트 임포트
from sqlalchemy.ext.asyncio import create_async_engine
from app.database import AsyncSessionLocal, engine, Base # engine, Base, AsyncSessionLocal이 필요합니다.
from app.models import Subsidy # Subsidy 모델 임포트
from app.config import settings

# --- 업데이트된 RAW_SUBSIDY_DATA (제조사, 모델명, 국비, 지방비, 총보조금 - 단위: 만원) ---
RAW_SUBSIDY_DATA: List[Tuple[str, str, int, int, int]] = [
    ("현대자동차", "GV60 스탠다드 2WD 19인치", 287, 148, 435),
    ("현대자동차", "GV60 스탠다드 AWD 19인치", 261, 135, 396),
    ("현대자동차", "GV60 스탠다드 AWD 20인치", 251, 129, 380),
    ("현대자동차", "GV60 퍼포먼스 AWD 21인치", 236, 122, 358),
    ("현대자동차", "Electrified GV70 AWD 20인치", 244, 126, 370),
    ("현대자동차", "Electrified GV70 AWD 19인치", 260, 134, 394),
    ("현대자동차", "아이오닉6 스탠다드 2WD 18인치", 635, 272, 907),
    ("현대자동차", "아이오닉6 롱레인지 2WD 18인치", 686, 297, 983),
    ("현대자동차", "아이오닉6 롱레인지 2WD 20인치", 680, 294, 974),
    ("현대자동차", "아이오닉6 롱레인지 AWD 18인치", 686, 297, 983),
    ("현대자동차", "아이오닉6 롱레인지 AWD 20인치", 647, 277, 924),
    ("현대자동차", "코나 일렉트릭 2WD 스탠다드 17인치", 573, 231, 804),
    ("현대자동차", "코나 일렉트릭 2WD 롱레인지 17인치", 623, 271, 894),
    ("현대자동차", "코나 일렉트릭 2WD 롱레인지 19인치(빌트인 캠)", 568, 242, 810),
    ("현대자동차", "아이오닉5 N", 232, 120, 352),
    ("현대자동차", "더뉴아이오닉5 2WD 롱레인지 19인치 빌트인 캠 미적용", 659, 298, 957),
    ("현대자동차", "더뉴아이오닉5 2WD 롱레인지 19인치", 656, 296, 952),
    ("현대자동차", "더뉴아이오닉5 2WD 롱레인지 20인치", 651, 294, 945),
    ("현대자동차", "더뉴아이오닉5 AWD 롱레인지 20인치", 624, 280, 904),
    ("현대자동차", "더뉴아이오닉5 AWD 롱레인지 19인치", 650, 293, 943),
    ("현대자동차", "더뉴아이오닉5 2WD 롱레인지 N라인 20인치", 633, 285, 918),
    ("현대자동차", "더뉴아이오닉5 AWD 롱레인지 N라인 20인치", 602, 268, 870),
    ("현대자동차", "Electrified G80 AWD 19인치(2025)", 275, 142, 417),
    ("현대자동차", "더뉴아이오닉5 2WD 스탠다드 19인치", 561, 255, 816),
    ("현대자동차", "Electrified GV70 AWD 20인치(2025)", 250, 129, 379),
    ("현대자동차", "Electrified GV70 AWD 19인치(2025)", 266, 137, 403),
    ("현대자동차", "코나 일렉트릭 2WD 롱레인지 17인치(빌트인 캠)", 623, 271, 894),
    ("현대자동차", "아이오닉9 성능형 AWD", 277, 143, 420),
    ("현대자동차", "아이오닉9 항속형 AWD", 276, 142, 418),
    ("현대자동차", "아이오닉9 항속형 2WD", 279, 144, 423),
    ("현대자동차", "GV60 퍼포먼스 AWD 21인치(2025)", 248, 128, 376),
    ("현대자동차", "GV60 스탠다드 AWD 20인치(2025)", 266, 137, 403),
    ("현대자동차", "GV60 스탠다드 AWD 19인치(2025)", 277, 143, 420),
    ("현대자동차", "GV60 스탠다드 2WD 19인치(2025)", 290, 150, 440),
    ("현대자동차", "더 뉴 아이오닉6 2wd 롱레인지 n라인 20인치", 580, 300, 880),
    ("현대자동차", "더 뉴 아이오닉6 awd 롱레인지 n라인 20인치", 547, 282, 829),
    ("현대자동차", "더 뉴 아이오닉6 2wd 롱레인지 18인치", 580, 300, 880),
    ("현대자동차", "더 뉴 아이오닉6 2wd 롱레인지 20인치", 580, 300, 880),
    ("현대자동차", "더 뉴 아이오닉6 awd 롱레인지 18인치", 580, 300, 880),
    ("현대자동차", "더 뉴 아이오닉6 awd 롱레인지 20인치", 563, 291, 854),
    ("현대자동차", "더 뉴 아이오닉6 2wd 스탠다드 18인치", 570, 294, 864),
    ("기아", "The all-new Kia Niro EV", 590, 258, 848),
    ("기아", "EV9 롱레인지 2WD 19인치", 275, 142, 417),
    ("기아", "EV9 롱레인지 2WD 20인치", 273, 141, 414),
    ("기아", "EV9 롱레인지 4WD 19인치", 259, 133, 392),
    ("기아", "EV9 롱레인지 4WD 21인치", 265, 137, 402),
    ("기아", "EV9 롱레인지 GTL 4WD 21인치", 257, 132, 389),
    ("기아", "더뉴EV6 롱레인지 4WD 20인치", 617, 280, 897),
    ("기아", "더뉴EV6 롱레인지 2WD 20인치", 644, 294, 938),
    ("기아", "더뉴EV6 롱레인지 4WD 19인치", 646, 295, 941),
    ("기아", "더뉴EV6 롱레인지 2WD 19인치", 655, 300, 955),
    ("기아", "EV3 롱레인지 2WD 17인치", 565, 292, 857),
    ("기아", "EV3 롱레인지 2WD 19인치", 565, 292, 857),
    ("기아", "EV3 스탠다드 2WD", 479, 247, 726),
    ("기아", "더뉴EV6 GT", 232, 120, 352),
    ("기아", "더뉴EV6 스탠다드", 582, 264, 846),
    ("기아", "EV9 스탠다드", 242, 125, 367),
    ("기아", "EV4 롱레인지 GTL 2WD 19인치", 565, 292, 857),
    ("기아", "EV4 스탠다드 2WD 19인치", 491, 253, 744),
    ("기아", "EV4 롱레인지 2WD 17인치", 565, 292, 857),
    ("기아", "EV4 롱레인지 2WD 19인치", 565, 292, 857),
    ("기아", "EV4 스탠다드 2WD 17인치", 522, 270, 792),
    ("기아", "PV5 패신저 5인승 롱레인지", 468, 242, 710),
    ("기아", "EV5 롱레인지 2WD", 562, 290, 852),
    ("르노코리아", "scenic", 443, 229, 672),
    ("BMW", "MINI Cooper SE", 303, 156, 459),
    ("BMW", "i4 eDrive40", 189, 97, 286),
    ("BMW", "i4 M50", 172, 88, 260),
    ("BMW", "iX1 xDrive30", 154, 79, 233),
    ("BMW", "i4 eDrive40 LCI", 187, 96, 283),
    ("BMW", "iX2 eDrive20", 167, 86, 253),
    ("BMW", "MINI Countryman SE ALL4", 158, 81, 239),
    ("BMW", "MINI Countryman E", 166, 85, 251),
    ("BMW", "MINI Aceman SE", 306, 158, 464),
    ("BMW", "i4 M50 LCI", 177, 91, 268),
    ("BMW", "MINI JCW Aceman E", 151, 78, 229),
    ("BMW", "MINI JCW E", 147, 76, 223),
    ("BMW", "MINI Aceman E", 306, 158, 464),
    ("BMW", "ix1 edrive20", 166, 85, 251),
    ("BMW", "i5 edrive 40", 198, 102, 300),
    ("테슬라코리아", "(단종)Model 3 RWD(2024)", 183, 94, 277),
    ("테슬라코리아", "Model 3 Long Range", 202, 104, 306),
    ("테슬라코리아", "(단종)Model Y RWD", 201, 87, 288),
    ("테슬라코리아", "(단종)Model Y Long Range", 184, 95, 279),
    ("테슬라코리아", "(단종)Model Y Performance", 191, 98, 289),
    ("테슬라코리아", "Model 3 Performance", 187, 96, 283),
    ("테슬라코리아", "(단종)Model Y Long Range 19인치", 202, 104, 306),
    ("테슬라코리아", "Model 3 RWD", 186, 96, 282),
    ("테슬라코리아", "New Model Y Long Range", 207, 107, 314),
    ("테슬라코리아", "New Model Y RWD", 188, 97, 285),
    ("메르세데스벤츠코리아", "(단종)EQB300 4MATIC(Pre-Facelift)(5인승)", 152, 78, 230)
]

def extract_model_group(model_name: str) -> str:
    """
    세부 모델명에서 모델 그룹 이름(예: 'GV60' 또는 'EV6')을 추출합니다.
    (첫 번째 공백 또는 숫자가 나오기 전까지의 문자열을 사용합니다.)
    """
    # 숫자(0-9) 또는 공백을 찾아서 그 앞부분을 그룹으로 추출
    match = re.match(r"([^\s\d]+)", model_name)
    if match:
        return match.group(1).upper() # 대문자로 변환하여 일관성 유지

    # 예외: Model 3처럼 공백 없이 숫자가 바로 붙는 경우, 또는 이름에 숫자가 포함된 경우
    # ex) 아이오닉5 -> 아이오닉5 / Model 3 -> Model
    # 여기서는 좀 더 정교하게 첫 번째 공백까지만 사용하거나, 특별 케이스를 처리합니다.
    if " " in model_name:
        first_word = model_name.split(" ")[0]
        # 아이오닉5, Model 3 등 숫자와 이름이 붙어있는 경우 처리
        if re.match(r"[A-Za-z]+[0-9]+", first_word) and not re.match(r"[0-9]", first_word):
            return first_word.upper()

    return model_name.split(" ")[0].upper() # 기본적으로 첫 번째 단어를 사용

async def initialize_subsidy_data():
    """
    DB에 보조금 초기 데이터를 대량 삽입합니다.
    """
    # ⚠️ 중요: init_db() 호출하여 Subsidy 테이블이 확실히 존재하도록 보장
    try:
        print("INFO: DB 테이블 생성 확인/초기화 중...")
        async with engine.begin() as conn:
            # Base.metadata에 등록된 모든 테이블을 생성합니다.
            await conn.run_sync(Base.metadata.create_all)
        print("INFO: DB 테이블 생성 확인 완료.")
    except Exception as e:
        print(f"FATAL ERROR: DB 테이블 초기화 중 오류 발생: {e}")
        return

    print("--- 🚀 보조금 데이터 초기화 시작 ---")

    # 1. 기존 데이터 삭제 (재실행을 위해)
    async with AsyncSessionLocal() as session:
        try:
            print("INFO: 기존 Subsidy 데이터 삭제 중...")
            await session.execute(Subsidy.__table__.delete())
            await session.commit()
            print("INFO: 기존 데이터 삭제 완료.")
        except Exception as e:
            await session.rollback()
            print(f"ERROR: 데이터 삭제 중 오류 발생: {e}")
            return

    # 2. 새로운 데이터 객체 생성 및 벌크 삽입
    subsidy_objects = []

    # ⚠️ 중요: CSV 데이터를 파싱하여 모델 그룹을 추출합니다.
    for manufacturer, model_name, national, local, total in RAW_SUBSIDY_DATA:
        # 모델 그룹 추출 로직
        model_group = extract_model_group(model_name)

        # 모델 그룹 추출이 예상과 다르게 작동하는 경우 디버깅용 로그
        # print(f"Raw: {model_name} -> Group: {model_group}")

        subsidy_objects.append(
            Subsidy(
                manufacturer=manufacturer,
                model_group=model_group,
                model_name=model_name,
                subsidy_national_10k_won=national,
                subsidy_local_10k_won=local,
                subsidy_total_10k_won=total,
            )
        )

    async with AsyncSessionLocal() as session:
        try:
            print(f"INFO: {len(subsidy_objects)}개의 보조금 데이터 삽입 중...")

            # bulk_save_objects를 사용하여 효율적으로 삽입
            session.bulk_save_objects(subsidy_objects)
            await session.commit()

            print("SUCCESS: 보조금 초기 데이터 삽입 완료!")
        except Exception as e:
            await session.rollback()
            print(f"FATAL ERROR: 데이터 삽입 중 치명적인 오류 발생: {e}")

if __name__ == "__main__":
    # 스크립트 실행
    asyncio.run(initialize_subsidy_data())