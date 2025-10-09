from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Optional

from app.models import User as DBUser
from app.schemas.user import UserCreate

async def get_user_by_username(db: AsyncSession, username: str) -> Optional[DBUser]:
    """사용자 이름으로 DB에서 사용자를 조회합니다."""
    stmt = select(DBUser).where(DBUser.username == username)
    result = await db.execute(stmt)
    return result.scalars().first()

# (필요 시) 사용자 생성 함수 (임시 관리자 계정 생성용)
async def create_user(db: AsyncSession, user: UserCreate, hashed_password: str) -> DBUser:
    """새로운 사용자를 생성합니다."""
    new_user = DBUser(
        username=user.username,
        email=user.email,
        role=user.role,
        hashed_password=hashed_password
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user
