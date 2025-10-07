from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Subsidy # Subsidy 모델 임포트

class SubsidyService:
    """
    보조금 데이터에 대한 DB 상호작용 로직을 처리하는 서비스 클래스입니다.
    이 클래스의 인스턴스가 router에서 직접 사용됩니다.
    """

    @staticmethod
    async def get_subsidy_info(
            db: AsyncSession,
            manufacturer: str,
            model_group: str
    ) -> List[Subsidy]:
        """
        제조사(manufacturer)와 모델 그룹명(model_group)을 기준으로
        해당 그룹에 속하는 모든 상세 보조금 정보를 조회합니다.

        Router에서 호출될 때, model_group은 대문자로 정규화되어 사용됩니다.
        """

        # 모델 그룹은 데이터 삽입 시 대문자로 저장되므로, 쿼리 시에도 대문자 변환을 적용합니다.
        normalized_model_group = model_group.upper()

        # 쿼리 구성: 제조사와 모델 그룹명이 모두 일치하는 행을 선택합니다.
        query = select(Subsidy).where(
            Subsidy.manufacturer == manufacturer,
            # 모델 그룹명이 해당 문자열로 시작하는 모든 상세 모델을 조회합니다.
            Subsidy.model_group.ilike(f"{normalized_model_group}%")
        ).order_by(Subsidy.model_name)

        result = await db.execute(query)

        # Subsidy 모델 인스턴스 리스트 반환
        return result.scalars().all()

# SubsidyService 클래스의 단일 인스턴스를 생성합니다.
# subsidy_router.py 파일에서 'from app.services.subsidy_service import subsidy_service'로
# 이 인스턴스를 임포트하여 사용합니다.
subsidy_service = SubsidyService()