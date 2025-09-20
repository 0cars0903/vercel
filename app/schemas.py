# app/schemas.py
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

# 공통 필드를 가진 기본 스키마
class ContactBase(BaseModel):
    name_ko: Optional[str] = None
    name_en: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    address: Optional[str] = None

# 연락처 생성을 위한 스키마 (API 요청 시 사용)
class ContactCreate(ContactBase):
    pass

# 연락처 조회를 위한 스키마 (API 응답 시 사용)
class Contact(ContactBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True # SQLAlchemy 모델을 Pydantic 모델로 자동 변환

# 연락처 수정을 위한 스키마 (모든 필드는 선택 사항)
class ContactUpdate(ContactBase):
    pass