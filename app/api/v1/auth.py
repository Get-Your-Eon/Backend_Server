from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from app.db.database import get_async_session
from app.auth import authenticate_user, create_access_token
from app.schemas.user import Token
from app.core.config import settings

# 라우터 인스턴스 생성
router = APIRouter(prefix="/auth", tags=["Auth & Users"])

@router.post("/token", response_model=Token, summary="관리자/사용자 로그인 및 JWT 토큰 발급")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), # username과 password를 form-data로 받음
    db: AsyncSession = Depends(get_async_session)
):
    """
    제공된 사용자 이름과 비밀번호로 사용자를 인증하고, 성공하면 Access Token을 반환합니다.
    """
    
    # 1. 사용자 인증 시도 (DB에서 사용자 정보를 가져오고 비밀번호를 검증)
    user = await authenticate_user(db, form_data.username, form_data.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 잘못되었습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 2. Access Token 생성
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # JWT 페이로드에 사용자 이름과 역할을 포함
    access_token = create_access_token(
        data={
            "sub_username": user.username,
            "role": user.role.value # Enum 값을 문자열로 변환
        },
        expires_delta=access_token_expires
    )
    
    # 3. 토큰 응답
    return {"access_token": access_token, "token_type": "bearer"}
