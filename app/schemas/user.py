from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum

# 사용자 역할 Enum 정의
class UserRole(str, Enum):
    """사용자의 역할을 정의합니다."""
    ADMIN = "admin"
    USER = "user"
    MANAGER = "manager"

# -----------------
# Pydantic Schemas
# -----------------

class UserBase(BaseModel):
    """사용자 기본 정보 스키마."""
    username: str = Field(..., max_length=50, example="admin_user")
    email: Optional[str] = Field(None, example="admin@codyssey.com")

class UserCreate(UserBase):
    """사용자 생성 스키마 (비밀번호 포함)."""
    password: str = Field(..., min_length=6)
    role: UserRole = Field(UserRole.USER, description="기본값은 일반 사용자(user)입니다.")

class UserInDB(UserBase):
    """DB 내부용 스키마 (보안 정보 포함)."""
    id: int
    role: UserRole
    hashed_password: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserResponse(UserBase):
    """클라이언트 응답용 스키마 (비밀번호 제외)."""
    id: int
    role: UserRole
    created_at: datetime

    class Config:
        from_attributes = True

# -----------------
# 인증 관련 Schemas
# -----------------

class Token(BaseModel):
    """JWT 토큰 응답 스키마."""
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    """JWT 페이로드 스키마."""
    username: Optional[str] = None
    role: Optional[UserRole] = None

class Login(BaseModel):
    """로그인 요청 스키마."""
    username: str
    password: str
