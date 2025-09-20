# app/crud.py
from sqlalchemy.orm import Session
from . import models, schemas

def create_contact(db: Session, contact: schemas.ContactCreate):
    """새로운 연락처를 DB에 저장합니다."""
    # Pydantic 모델을 SQLAlchemy 모델로 변환
    db_contact = models.Contact(**contact.model_dump())
    db.add(db_contact)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def get_contact(db: Session, contact_id: int):
    """ID로 특정 연락처를 조회합니다."""
    return db.query(models.Contact).filter(models.Contact.id == contact_id).first()

def get_contacts(db: Session, skip: int = 0, limit: int = 100):
    """모든 연락처 목록을 조회합니다."""
    return db.query(models.Contact).offset(skip).limit(limit).all()

def update_contact(db: Session, contact_id: int, contact: schemas.ContactUpdate):
    """ID로 특정 연락처를 찾아 정보를 수정합니다."""
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if db_contact:
        # Pydantic 모델을 dict로 변환하고, 값이 있는 필드만 업데이트
        update_data = contact.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_contact, key, value)
        db.commit()
        db.refresh(db_contact)
    return db_contact

def delete_contact(db: Session, contact_id: int):
    """ID로 특정 연락처를 찾아 삭제합니다."""
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if db_contact:
        db.delete(db_contact)
        db.commit()
    return db_contact