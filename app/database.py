# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. 데이터베이스 접속 주소 설정 (SQLite 사용)
#    프로젝트 루트 폴더에 contacts.db 파일이 생성됩니다.
SQLALCHEMY_DATABASE_URL = "sqlite:///../contacts.db"

# 2. 데이터베이스 엔진 생성
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

# 3. 데이터베이스와 상호작용하기 위한 세션 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 4. 모델 클래스들이 상속받을 Base 클래스 생성
Base = declarative_base()

# DB 세션을 가져오는 함수 (Dependency)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()