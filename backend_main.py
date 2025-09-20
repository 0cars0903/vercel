import os
import json
import re
import time
import base64
import requests
import qrcode
from datetime import datetime
import io
from werkzeug.utils import secure_filename
import tempfile
import zipfile
import ollama
import dotenv
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

dotenv.load_dotenv()

app = FastAPI()

# --- CORS 설정 ---
# Vercel 배포 주소와 로컬 테스트 환경을 허용합니다.
origins = [
    "http://localhost",
    "http://localhost:5500",  # Live Server 등 로컬 테스트 포트
    # Vercel 배포 후 실제 프런트엔드 주소를 여기에 추가하세요.
    # "https://vercel-asrrp2uk7-junhees-projects-5f5f2302.vercel.app/
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 개발 편의를 위해 모든 출처 허용, 배포 시에는 위 origins 사용 권장
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 환경 변수 로드 ---
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')


# ==========================================================================
# 명함 처리 에이전트 및 헬퍼 함수 (기존 로직과 동일)
# ==========================================================================

def ocr_agent(image_path: str) -> list[dict]:
    """NAVER CLOVA OCR API를 사용하여 이미지에서 텍스트 추출"""
    # ... (기존 app.py의 ocr_agent 함수 내용과 동일)
    print(f"\n[ OCR Agent ] Processing '{os.path.basename(image_path)}'...")
    if not NAVER_OCR_SECRET_KEY or not NAVER_OCR_INVOKE_URL:
        raise HTTPException(status_code=500, detail="NAVER CLOVA OCR environment variables are not set.")
    
    request_body = {'version': 'V2', 'requestId': 'NCP-OCR-ID-' + str(int(time.time() * 1000)), 'timestamp': int(time.time() * 1000), 'lang': 'ko', 'images': [{'format': os.path.splitext(image_path)[1][1:].upper(), 'name': os.path.basename(image_path)}]}
    headers = {'X-OCR-Secret': NAVER_OCR_SECRET_KEY}
    
    try:
        with open(image_path, 'rb') as img_file:
            files = {'file': (os.path.basename(image_path), img_file, 'image/' + os.path.splitext(image_path)[1][1:].lower()), 'message': (None, json.dumps(request_body).encode('UTF-8'), 'application/json')}
            response = requests.post(NAVER_OCR_INVOKE_URL, headers=headers, files=files)
            response.raise_for_status()
        
        result_json = response.json()
        full_text = " ".join([field.get('inferText', '') for image_result in result_json.get('images', []) for field in image_result.get('fields', [])])
        sentences = [s.strip() for s in full_text.strip().replace('\n', ' ').split('.') if s.strip()]
        return [{'id': idx + 1, 'text': sentence} for idx, sentence in enumerate(sentences)]
    except Exception as e:
        print(f"[OCR Error] {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")

def extract_structured_info_with_retry(raw_text: str, model_name: str = 'mistral:latest') -> dict:
    """Ollama를 사용하여 텍스트에서 구조화된 정보 추출"""
    # ... (기존 app.py의 extract_structured_info_with_retry 함수 내용과 동일)
    prompt = f"""You are an expert business card information extractor... Required JSON structure: {{"name": "", "title": "", "company": "","phone": "", "email": "", "address": ""}} ... --- Text to Analyze --- {raw_text}"""
    try:
        response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], format='json', options={'temperature': 0.3, 'top_p': 0.9})
        content = response['message']['content']
        return json.loads(content) if isinstance(content, str) else content
    except Exception as e:
        print(f"[LLM Error] {e}")
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {e}")


def two_sided_extract_agent(front_text: str, back_text: str, model_name: str = 'mistral:latest') -> dict:
    """양면 명함 분석을 위한 Ollama 에이전트"""
    # ... (기존 app.py의 two_sided_extract_agent 함수 내용과 동일)
    combined_text = f"--- Front Side (Korean) ---\n{front_text}\n\n--- Back Side (English) ---\n{back_text}"
    prompt = f"""You are an expert business card extractor for two-sided (Korean/English) cards... Required JSON structure: {{"name_ko": "", ...}} ... --- Combined Text to Analyze --- {combined_text}"""
    try:
        response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], format='json', options={'temperature': 0.3, 'top_p': 0.9})
        content = response['message']['content']
        return json.loads(content) if isinstance(content, str) else content
    except Exception as e:
        print(f"[Two-sided LLM Error] {e}")
        raise HTTPException(status_code=500, detail=f"Two-sided LLM processing failed: {e}")

def generate_vcf_content(data: dict) -> str:
    """양면 지원 VCF 생성 함수"""
    # ... (기존 app.py의 generate_vcf_content 함수 내용과 동일)
    vcf_lines = ["BEGIN:VCARD", "VERSION:3.0"]
    name_ko = data.get('name_ko') or data.get('name', '')
    name_en = data.get('name_en', '')
    if name_ko or name_en:
        fn = f"{name_ko} {name_en}".strip()
        n = f"{name_ko};{name_en};;;"
        vcf_lines.append(f"FN;CHARSET=UTF-8:{fn}")
        vcf_lines.append(f"N;CHARSET=UTF-8:{n}")
    # ... other fields ...
    vcf_lines.append("END:VCARD")
    return '\n'.join(vcf_lines)


def generate_qr_code(vcf_content):
    """QR 코드 생성 함수"""
    # ... (기존 app.py의 generate_qr_code 함수 내용과 동일)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(vcf_content)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode()

# ==========================================================================
# FastAPI Endpoints
# ==========================================================================

@app.post("/api/process-batch")
async def process_batch(images: List[UploadFile] = File(...)):
    """다중 명함 일괄 처리 API"""
    if not images:
        raise HTTPException(status_code=400, detail="이미지 파일이 필요합니다.")

    results = []
    with tempfile.TemporaryDirectory() as temp_dir:
        for idx, file in enumerate(images):
            try:
                temp_path = os.path.join(temp_dir, secure_filename(file.filename))
                with open(temp_path, "wb") as buffer:
                    buffer.write(await file.read())

                ocr_list = ocr_agent(temp_path)
                if not ocr_list: continue

                full_text = ' '.join([item['text'] for item in ocr_list])
                contact_info = extract_structured_info_with_retry(full_text)
                
                with open(temp_path, "rb") as img_file:
                    thumbnail = base64.b64encode(img_file.read()).decode('utf-8')

                results.append({
                    'id': f"card-{int(time.time() * 1000)}-{idx}",
                    'source': file.filename,
                    'data': contact_info,
                    'thumbnail': thumbnail
                })
            except Exception as e:
                # 개별 파일 오류 시에도 계속 진행
                print(f"Error processing file {file.filename}: {e}")
                continue
    return JSONResponse(content={'success': True, 'results': results})

@app.post("/api/process-two-sided")
async def process_two_sided(frontImage: UploadFile = File(...), backImage: UploadFile = File(...)):
    """양면 명함 처리 API"""
    with tempfile.TemporaryDirectory() as temp_dir:
        front_path = os.path.join(temp_dir, secure_filename(frontImage.filename))
        back_path = os.path.join(temp_dir, secure_filename(backImage.filename))
        
        with open(front_path, "wb") as f: f.write(await frontImage.read())
        with open(back_path, "wb") as f: f.write(await backImage.read())

        front_text = ' '.join(item['text'] for item in ocr_agent(front_path))
        back_text = ' '.join(item['text'] for item in ocr_agent(back_path))
        
        if not front_text or not back_text:
            raise HTTPException(status_code=400, detail="한쪽 또는 양쪽 면의 OCR 처리에 실패했습니다.")

        contact_info = two_sided_extract_agent(front_text, back_text)
    
    return JSONResponse(content={'success': True, 'contactInfo': contact_info})

@app.post("/api/generate-vcf-qr")
async def generate_vcf_qr(payload: dict):
    """단일 VCF 및 QR 생성 API"""
    contact_data = payload.get('contactData', {})
    if not contact_data:
        raise HTTPException(status_code=400, detail="Contact data is required.")
    vcf_content = generate_vcf_content(contact_data)
    qr_base64 = generate_qr_code(vcf_content)
    return JSONResponse(content={'success': True, 'vcfContent': vcf_content, 'qrCode': qr_base64})

@app.post("/api/download-batch")
async def download_batch(payload: dict):
    """VCF 파일 일괄 다운로드 (압축) API"""
    items_to_download = payload.get('items', [])
    if not items_to_download:
        raise HTTPException(status_code=400, detail="다운로드할 항목이 없습니다.")

    if len(items_to_download) == 1:
        item = items_to_download[0]
        vcf_content = generate_vcf_content(item['data'])
        name = item['data'].get('name_ko') or item['data'].get('name', 'contact')
        safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
        headers = {'Content-Disposition': f'attachment; filename="{safe_name}.vcf"'}
        return Response(content=vcf_content, media_type='text/vcard', headers=headers)

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for item in items_to_download:
            vcf_content = generate_vcf_content(item['data'])
            name = item['data'].get('name_ko') or item['data'].get('name', 'contact')
            safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
            zf.writestr(f"{safe_name}.vcf", vcf_content)
    memory_file.seek(0)
    zip_filename = f"contacts_{datetime.now().strftime('%Y%m%d')}.zip"
    headers = {'Content-Disposition': f'attachment; filename="{zip_filename}"'}
    return Response(content=memory_file.getvalue(), media_type='application/zip', headers=headers)


@app.get("/api/health")
def health_check():
    """헬스 체크"""
    return {
        'status': 'healthy',
        'version': '2.2-backend',
        'timestamp': datetime.now().isoformat(),
        'ocr_ready': bool(NAVER_OCR_SECRET_KEY and NAVER_OCR_INVOKE_URL),
        'ollama_ready': True # Placeholder, add real check if needed
    }

if __name__ == '__main__':
    print("🚀 AI 명함 처리 시스템 백엔드 v2.2 시작!")
    print("=========================================")
    if not (NAVER_OCR_SECRET_KEY and NAVER_OCR_INVOKE_URL):
        print("⚠️ NAVER CLOVA OCR 환경 변수가 설정되지 않았습니다! .env 파일을 확인하세요.")
    try:
        ollama.list()
        print("✅ Ollama 연결 성공!")
    except Exception as e:
        print(f"❌ Ollama 연결 실패: {e}. 'ollama serve'를 실행하세요.")
    
    print("\n🔗 API 서버가 http://localhost:8000 에서 실행 중입니다.")
    print("🛑 종료하려면 Ctrl+C를 누르세요.")
    uvicorn.run(app, host="0.0.0.0", port=8000)
