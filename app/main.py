import os
import json
import re
import time
import base64
import requests
import qrcode
import io
import tempfile
import zipfile
import ollama
import dotenv
from typing import List
from datetime import datetime
from werkzeug.utils import secure_filename

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# 내부 모듈 import
from . import crud, models, schemas
from .database import engine, get_db

dotenv.load_dotenv()

# DB 테이블 생성 (Alembic을 사용하지 않을 경우에만 활성화)
# models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- CORS 설정 ---
# app/main.py

# ... (다른 import문) ...

app = FastAPI()

# --- CORS 설정 ---
# 허용할 출처 목록을 정의합니다. (중복 및 마지막 슬래시 제거)
origins = [
    "http://localhost",
    "http://localhost:5173",
    "https://vercel-tawny-delta.vercel.app/"  # 실제 배포 도메인 추가
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 👈 이 부분을 ["*"]에서 origins 변수로 변경!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... (이하 API 엔드포인트 코드) ...

# --- 환경 변수 로드 ---
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')

# ==========================================================================
# 명함 처리 에이전트 및 헬퍼 함수 (기존 로직과 동일)
# ==========================================================================

def ocr_agent(image_path: str) -> str:
    """NAVER CLOVA OCR API를 사용하여 이미지에서 전체 텍스트를 추출"""
    print(f"\n[ OCR Agent ] Processing '{os.path.basename(image_path)}'...")
    # ... (기존 ocr_agent 로직, 단 마지막에 full_text를 반환하도록 수정)
    try:
        # ... (request, response 부분은 동일) ...
        result_json = requests.post(NAVER_OCR_INVOKE_URL, headers={'X-OCR-Secret': NAVER_OCR_SECRET_KEY}, files={'file': open(image_path, 'rb'), 'message': json.dumps({'version': 'V2', 'requestId': 'id', 'timestamp': 0, 'lang': 'ko', 'images': [{'format': 'PNG', 'name': 'img'}]})}).json()
        full_text = " ".join([field.get('inferText', '') for image in result_json.get('images', []) for field in image.get('fields', [])])
        return full_text.strip().replace('\n', ' ')
    except Exception as e:
        print(f"[OCR Error] {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")

def extract_structured_info(raw_text: str) -> dict:
    """Ollama를 사용하여 텍스트에서 구조화된 정보 추출 (단면용)"""
    prompt = f"""You are an expert business card information extractor. From the text below, extract the person's name, title, company, phone number, email, and address. The name is the most important field.
    Required JSON structure: {{"name_ko": "", "title": "", "company": "","phone": "", "email": "", "address": ""}}
    ---
    Text to Analyze: {raw_text}"""
    try:
        response = ollama.chat(model='mistral:latest', messages=[{'role': 'user', 'content': prompt}], format='json')
        return json.loads(response['message']['content'])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {e}")

def two_sided_extract_agent(front_text: str, back_text: str) -> dict:
    """양면 명함 분석을 위한 Ollama 에이전트"""
    combined_text = f"--- Front Side (Korean) ---\n{front_text}\n\n--- Back Side (English) ---\n{back_text}"
    prompt = f"""Extract information from a two-sided business card.
    Required JSON structure: {{"name_ko": "", "name_en": "", "title": "", "company": "", "phone": "", "email": "", "address": ""}}
    ---
    Combined Text to Analyze: {combined_text}"""
    try:
        response = ollama.chat(model='mistral:latest', messages=[{'role': 'user', 'content': prompt}], format='json')
        return json.loads(response['message']['content'])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Two-sided LLM processing failed: {e}")

# ... (generate_vcf_content, generate_qr_code 함수는 기존과 동일하게 유지)

# ==========================================================================
# FastAPI Endpoints
# ==========================================================================

@app.post("/api/process-batch", response_model=List[schemas.Contact])
async def process_batch(images: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    """다중 명함 일괄 처리 및 DB 저장"""
    if not images:
        raise HTTPException(status_code=400, detail="이미지 파일이 필요합니다.")

    created_contacts = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for file in images:
            try:
                temp_path = os.path.join(temp_dir, secure_filename(file.filename))
                with open(temp_path, "wb") as buffer:
                    buffer.write(await file.read())

                full_text = ocr_agent(temp_path)
                if not full_text: continue
                
                contact_info = extract_structured_info(full_text)
                
                contact_to_create = schemas.ContactCreate(**contact_info)
                created_contact = crud.create_contact(db=db, contact=contact_to_create)
                created_contacts.append(created_contact)

            except Exception as e:
                print(f"Error processing file {file.filename}: {e}")
                continue
                
    return created_contacts

@app.post("/api/process-two-sided", response_model=schemas.Contact)
async def process_two_sided(frontImage: UploadFile = File(...), backImage: UploadFile = File(...), db: Session = Depends(get_db)):
    """양면 명함 처리 및 DB 저장"""
    with tempfile.TemporaryDirectory() as temp_dir:
        front_path = os.path.join(temp_dir, secure_filename(frontImage.filename))
        back_path = os.path.join(temp_dir, secure_filename(backImage.filename))
        
        with open(front_path, "wb") as f: f.write(await frontImage.read())
        with open(back_path, "wb") as f: f.write(await backImage.read())

        front_text = ocr_agent(front_path)
        back_text = ocr_agent(back_path)
        
        contact_info = two_sided_extract_agent(front_text, back_text)
        
        contact_to_create = schemas.ContactCreate(**contact_info)
        created_contact = crud.create_contact(db=db, contact=contact_to_create)
        return created_contact

@app.get("/api/contacts/", response_model=List[schemas.Contact])
def read_contacts(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """저장된 모든 연락처 목록 조회"""
    contacts = crud.get_contacts(db, skip=skip, limit=limit)
    return contacts

@app.get("/api/contacts/{contact_id}", response_model=schemas.Contact)
def read_contact(contact_id: int, db: Session = Depends(get_db)):
    """특정 ID의 연락처 정보 조회"""
    db_contact = crud.get_contact(db, contact_id=contact_id)
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

# [신규] 연락처 수정 API
@app.put("/api/contacts/{contact_id}", response_model=schemas.Contact)
def update_contact_api(contact_id: int, contact: schemas.ContactUpdate, db: Session = Depends(get_db)):
    """특정 ID의 연락처 정보를 수정합니다."""
    db_contact = crud.update_contact(db=db, contact_id=contact_id, contact=contact)
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

# [신규] 연락처 삭제 API
@app.delete("/api/contacts/{contact_id}", response_model=schemas.Contact)
def delete_contact_api(contact_id: int, db: Session = Depends(get_db)):
    """특정 ID의 연락처를 삭제합니다."""
    db_contact = crud.delete_contact(db=db, contact_id=contact_id)
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
    return db_contact

@app.get("/api/health")
def health_check():
    """헬스 체크"""
    return {"status": "healthy", "version": "3.0-db"}
