from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Subsidy  # Subsidy 모델 임포트
from app.schemas.subsidy import SubsidyPublic  # 수정: SubsidyResponse → SubsidyPublic

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
    ) -> List[SubsidyPublic]:
        """
        제조사(manufacturer)와 모델 그룹명(model_group)을 기준으로
        해당 그룹에 속하는 모든 상세 보조금 정보를 조회합니다.
        """

        # 입력값 공백 제거 및 None 처리
        manufacturer = (manufacturer or "").strip()
        normalized_model_group = (model_group or "").strip()

        # 쿼리 구성: 제조사와 모델 그룹명이 일치하는 행 조회
        query = select(Subsidy).where(
            Subsidy.manufacturer == manufacturer,
            Subsidy.model_group.ilike(f"{normalized_model_group}%")
        ).order_by(Subsidy.model_name)

        result = await db.execute(query)
        subsidies = result.scalars().all()

        # DB 모델을 API 응답용 스키마로 변환
        return [
            SubsidyPublic(
                model_name=s.model_name,
                subsidy_national_10k_won=s.subsidy_national_10k_won,
                subsidy_local_10k_won=s.subsidy_local_10k_won,
                subsidy_total_10k_won=s.subsidy_total_10k_won
            )
            for s in subsidies
        ]

# SubsidyService 클래스의 단일 인스턴스 생성
subsidy_service = SubsidyService()
