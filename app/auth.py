from datetime import datetime, timedelta, timezone
from typing import Optional

from passlib.context import CryptContext
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.schemas.user import TokenData, UserRole
from app.core.config import settings
from app.db.repository.user import get_user_by_username # 사용자 레포지토리에서 가져옴


from sqlalchemy.ext.asyncio import AsyncSession
from app.models import User as DBUser

# 비밀번호 해싱 컨텍스트 설정
# schemes: 사용할 해싱 알고리즘 (bcrypt가 널리 사용됨)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer 설정 (토큰을 추출할 엔드포인트 설정)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="v1/auth/token") # 토큰 발급 API 경로

# -----------------------------------------------------------
# 1. 비밀번호 해싱 및 검증
# -----------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """일반 비밀번호와 해시된 비밀번호를 비교합니다."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """비밀번호를 해시합니다."""
    return pwd_context.hash(password)

# -----------------------------------------------------------
# 2. JWT 토큰 생성 및 디코딩
# -----------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWT Access Token을 생성합니다."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # 기본 만료 시간: 1시간
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "sub": "access"})
    
    # settings.SECRET_KEY와 settings.ALGORITHM은 app/core/config.py에서 설정된 값을 사용합니다.
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenData]:
    """JWT 토큰을 디코딩하고 검증합니다."""
    try:
        # 토큰 디코딩
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        
        # 페이로드에서 사용자 이름과 역할을 추출하여 TokenData 객체로 반환
        username: str = payload.get("sub_username")
        role: str = payload.get("role")
        
        if username is None or role is None:
            return None
        
        return TokenData(username=username, role=UserRole(role))

    except JWTError:
        # JWTError 발생 시 (만료, 변조 등)
        return None

# -----------------------------------------------------------
# 3. 종속성 주입 (Dependency Injection) 함수
# -----------------------------------------------------------

def get_current_user_data(token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    HTTP 요청 헤더에서 JWT 토큰을 추출하고 검증하여 사용자 데이터를 반환합니다.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # 토큰 디코딩 및 검증
    token_data = decode_access_token(token)
    
    if token_data is None:
        raise credentials_exception
    
    return token_data

# -----------------------------------------------------------
# 4. 역할 기반 권한 검증 함수
# -----------------------------------------------------------

def check_admin_permission(current_user: TokenData = Depends(get_current_user_data)):
    """현재 사용자가 관리자(ADMIN)인지 확인하는 종속성 함수."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )
    # 관리자라면 TokenData를 반환하며 통과
    return current_user

# -----------------------------------------------------------
# 5. 사용자 인증 함수 (DB 접근 필요)
# -----------------------------------------------------------

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[DBUser]:
    """
    사용자 이름과 비밀번호를 검증하고 DB 사용자 객체를 반환합니다.
    """
    # 1. DB에서 사용자 이름으로 사용자 객체 조회
    user = await get_user_by_username(db, username=username)

    if not user:
        return None # 사용자 이름 없음

    # 2. 비밀번호 검증
    if not verify_password(password, user.hashed_password):
        return None # 비밀번호 불일치

    return user

