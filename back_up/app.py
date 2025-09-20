from flask import Flask, request, jsonify, render_template_string, send_file, make_response
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

# --- pipeline_card.py의 핵심 로직 통합 ---
import ollama
import dotenv
dotenv.load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size

# 환경 변수
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')

# ==========================================================================
# ⚙️ 명함 처리 에이전트 및 헬퍼 함수 (pipeline_card.py에서 가져옴)
# ==========================================================================

def ocr_agent(image_path: str) -> list[dict]:
    # ... (기존 ocr_agent 함수와 동일)
    print(f"\n[ OCR Agent ] Processing '{os.path.basename(image_path)}'...")
    request_body = {
        'version': 'V2', 'requestId': 'NCP-OCR-ID-' + str(int(time.time() * 1000)),
        'timestamp': int(time.time() * 1000), 'lang': 'ko',
        'images': [{'format': os.path.splitext(image_path)[1][1:].upper(), 'name': os.path.basename(image_path)}]
    }
    headers = {'X-OCR-Secret': NAVER_OCR_SECRET_KEY}
    try:
        with open(image_path, 'rb') as img_file:
            files = {
                'file': (os.path.basename(image_path), img_file, 'image/' + os.path.splitext(image_path)[1][1:].lower()),
                'message': (None, json.dumps(request_body).encode('UTF-8'), 'application/json')
            }
            response = requests.post(NAVER_OCR_INVOKE_URL, headers=headers, files=files)
            response.raise_for_status()
        result_json, full_text = response.json(), ""
        for image_result in result_json.get('images', []):
            for field in image_result.get('fields', []):
                full_text += field.get('inferText', '') + " "
        import kss
        sentences = kss.split_sentences(full_text.strip().replace('\n', ' '))
        return [{'id': idx + 1, 'text': s.strip()} for idx, s in enumerate(sentences) if s.strip()]
    except Exception as e:
        print(f"[OCR Error] {e}")
        return []

def extract_structured_info_with_retry(raw_text: str, model_name: str = 'mistral:latest') -> dict:
    # ... (pipeline_card.py의 단일 언어 추출 함수)
    prompt = f"""You are an expert business card information extractor. From the provided text, extract the required information into a valid JSON format. For missing information, use an empty string "". Return ONLY valid JSON.
    Required JSON structure: {{"name": "", "title": "", "company": "", "phone": "", "email": "", "address": ""}}
    --- Text to Analyze ---
    {raw_text}"""
    try:
        response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], format='json')
        return json.loads(response['message']['content'])
    except Exception:
        return {"name": "", "title": "", "company": "", "phone": "", "email": "", "address": ""}

def two_sided_extract_agent(front_text: str, back_text: str, model_name: str = 'mistral:latest') -> dict:
    # ... (pipeline_card.py의 양면 분석 에이전트)
    combined_text = f"--- Front Side (Korean) ---\n{front_text}\n\n--- Back Side (English) ---\n{back_text}"
    prompt = f"""You are an expert business card extractor for two-sided (Korean/English) cards. The provided text contains text from both sides. Extract the information into the following JSON structure.
    - Fill `_ko` fields from Korean text and `_en` fields from English text.
    - For missing information, use an empty string "".
    - `phone` and `email` are usually the same on both sides.
    - Return ONLY valid JSON.
    Required JSON structure: {{"name_ko": "", "name_en": "", "title_ko": "", "title_en": "", "company_ko": "", "company_en": "", "phone": "", "email": "", "address_ko": "", "address_en": ""}}
    --- Combined Text to Analyze ---
    {combined_text}"""
    try:
        response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], format='json')
        return json.loads(response['message']['content'])
    except Exception:
         return {"name_ko": "", "name_en": "", "title_ko": "", "title_en": "", "company_ko": "", "company_en": "", "phone": "", "email": "", "address_ko": "", "address_en": ""}


def generate_vcf_content(data: dict) -> str:
    # ... (pipeline_card.py의 양면 지원 VCF 생성 함수)
    vcf_lines = ["BEGIN:VCARD", "VERSION:3.0"]
    if 'name_ko' in data: # 양면 데이터 처리
        name_ko, name_en = data.get('name_ko'), data.get('name_en')
        title_ko, title_en = data.get('title_ko'), data.get('title_en')
        if name_ko or name_en:
            vcf_lines.append(f"N;CHARSET=UTF-8:{name_ko};{name_en};;;")
            vcf_lines.append(f"FN;CHARSET=UTF-8:{name_ko}{' ' if name_ko and name_en else ''}{name_en}")
        if title_ko or title_en:
            vcf_lines.append(f"TITLE;CHARSET=UTF-8:{title_ko}{' / ' if title_ko and title_en else ''}{title_en}")
        vcf_lines.append(f"ORG;CHARSET=UTF-8:{data.get('company_ko', '')}")
    else: # 단면 데이터 처리
        if data.get('name'): vcf_lines.append(f"FN:{data['name']}\nN:{data['name']};;;;")
        if data.get('title'): vcf_lines.append(f"TITLE:{data['title']}")
        if data.get('company'): vcf_lines.append(f"ORG:{data['company']}")
    # 공통 필드
    if data.get('phone'): vcf_lines.append(f"TEL;TYPE=WORK,VOICE:{data['phone']}")
    if data.get('email'): vcf_lines.append(f"EMAIL;TYPE=WORK:{data['email']}")
    address = data.get('address_ko', '') or data.get('address', '')
    if address: vcf_lines.append(f"ADR;TYPE=WORK;CHARSET=UTF-8:;;{address};;;;")
    vcf_lines.append(f"REV:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}\nEND:VCARD")
    return '\n'.join(vcf_lines)

def generate_qr_code(vcf_content):
    # ... (기존 QR 코드 생성 함수와 동일)
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(vcf_content)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="black", back_color="white")
    img_buffer = io.BytesIO()
    qr_image.save(img_buffer, format='PNG')
    return base64.b64encode(img_buffer.getvalue()).decode()

# ==========================================================================
# 🌐 Flask API Endpoints
# ==========================================================================

@app.route('/')
def index():
    with open("templates/index.html", "r", encoding="utf-8") as f:
        return render_template_string(f.read())

@app.route('/api/process-batch', methods=['POST'])
def process_batch():
    """다중 명함 일괄 처리 API"""
    try:
        files = request.files.getlist('images')
        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': '이미지 파일이 필요합니다.'})

        results = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for file in files:
                filename = secure_filename(file.filename)
                temp_path = os.path.join(temp_dir, filename)
                file.save(temp_path)
                
                ocr_list = ocr_agent(temp_path)
                if not ocr_list:
                    continue
                
                full_text = ' '.join([item['text'] for item in ocr_list])
                contact_info = extract_structured_info_with_retry(full_text)
                
                # 이미지 썸네일 생성
                file.seek(0)
                thumbnail = base64.b64encode(file.read()).decode('utf-8')

                results.append({
                    'id': f"card-{int(time.time() * 1000)}-{len(results)}",
                    'source': filename,
                    'data': contact_info,
                    'thumbnail': thumbnail
                })
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/process-two-sided', methods=['POST'])
def process_two_sided():
    """양면 명함 처리 API"""
    try:
        front_file = request.files.get('frontImage')
        back_file = request.files.get('backImage')
        if not front_file or not back_file:
            return jsonify({'success': False, 'error': '앞면과 뒷면 이미지가 모두 필요합니다.'})

        with tempfile.TemporaryDirectory() as temp_dir:
            front_path = os.path.join(temp_dir, secure_filename(front_file.filename))
            back_path = os.path.join(temp_dir, secure_filename(back_file.filename))
            front_file.save(front_path)
            back_file.save(back_path)

            front_ocr = ocr_agent(front_path)
            back_ocr = ocr_agent(back_path)
            if not front_ocr or not back_ocr:
                return jsonify({'success': False, 'error': '한쪽 또는 양쪽 면의 OCR 처리에 실패했습니다.'})
            
            front_text = ' '.join([item['text'] for item in front_ocr])
            back_text = ' '.join([item['text'] for item in back_ocr])

            contact_info = two_sided_extract_agent(front_text, back_text)
        
        return jsonify({'success': True, 'contactInfo': contact_info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/generate-vcf-qr', methods=['POST'])
def generate_vcf_qr():
    """단일 VCF 및 QR 생성 API"""
    try:
        contact_data = request.get_json().get('contactData', {})
        vcf_content = generate_vcf_content(contact_data)
        qr_base64 = generate_qr_code(vcf_content)
        return jsonify({'success': True, 'vcfContent': vcf_content, 'qrCode': qr_base64})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download-batch', methods=['POST'])
def download_batch():
    """VCF 파일 일괄 다운로드 (압축) API"""
    try:
        items_to_download = request.get_json().get('items', [])
        if not items_to_download:
            return jsonify({'success': False, 'error': '다운로드할 항목이 없습니다.'})

        with tempfile.TemporaryDirectory() as temp_dir:
            vcf_files = []
            for item in items_to_download:
                vcf_content = generate_vcf_content(item['data'])
                name = item['data'].get('name_ko') or item['data'].get('name', 'contact')
                safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
                vcf_filename = os.path.join(temp_dir, f"{safe_name}.vcf")
                with open(vcf_filename, 'w', encoding='utf-8') as f:
                    f.write(vcf_content)
                vcf_files.append(vcf_filename)

            if len(vcf_files) >= 5:
                zip_filename = os.path.join(temp_dir, f"contacts_{datetime.now().strftime('%Y%m%d')}.zip")
                with zipfile.ZipFile(zip_filename, 'w') as zf:
                    for file in vcf_files:
                        zf.write(file, os.path.basename(file))
                
                return send_file(zip_filename, as_attachment=True, download_name=os.path.basename(zip_filename))
            elif vcf_files: # 4개 이하일 경우 첫번째 VCF 파일만 다운로드
                return send_file(vcf_files[0], as_attachment=True, download_name=os.path.basename(vcf_files[0]))

        return jsonify({'success': False, 'error': '파일 생성 실패'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    os.makedirs("templates", exist_ok=True)
    # HTML 템플릿 파일 생성
    # (실제 배포 시에는 별도 파일로 관리하는 것이 좋음)
    from back_up.app_template import HTML_TEMPLATE
    with open("templates/index.html", "w", encoding="utf-8") as f:
        f.write(HTML_TEMPLATE)
    app.run(debug=True, port=5001)
