# app/models.py
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from .database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    name_ko = Column(String, index=True)
    name_en = Column(String)
    title = Column(String)
    company = Column(String, index=True)
    phone = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    address = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())