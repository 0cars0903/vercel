import ollama
import os
import json
import re
import time
from PIL import Image, ImageEnhance
import io
import base64
import requests
import qrcode
from datetime import datetime
import kss  # 한국어 문장 분리 라이브러리
import zipfile # 압축 파일 생성을 위한 라이브러리

# --- .env 파일에서 환경 변수 로드 ---
import dotenv
dotenv.load_dotenv()

# NAVER CLOVA OCR 환경 변수
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')

# --------------------------------------------------------------------------
# 🤖 Agent 1: OCR Agent (Naver Cloud OCR 사용) - 기존과 동일
# --------------------------------------------------------------------------
def ocr_agent(image_path: str) -> list[dict]:
    print(f"\n[ OCR Agent using Naver Cloud OCR ] '{os.path.basename(image_path)}' 이미지 처리 시작...")
    
    # 1. 요청에 필요한 정보 구성
    request_body = {
        'version': 'V2',
        'requestId': 'NCP-OCR-ID-' + str(int(time.time() * 1000)), 
        'timestamp': int(time.time() * 1000),
        'lang': 'ko', 
        'images': [
            {
                'format': os.path.splitext(image_path)[1][1:].upper(),
                'name': os.path.basename(image_path),
            }
        ]
    }
    
    headers = { 'X-OCR-Secret': NAVER_OCR_SECRET_KEY }

    try:
        with open(image_path, 'rb') as img_file:
            files = {
                'file': (os.path.basename(image_path), img_file, 'image/' + os.path.splitext(image_path)[1][1:].lower()),
                'message': (None, json.dumps(request_body).encode('UTF-8'), 'application/json')
            }
            response = requests.post(NAVER_OCR_INVOKE_URL, headers=headers, files=files)
            response.raise_for_status()

        result_json = response.json()
        
        full_text = ""
        for image_result in result_json.get('images', []):
            for field in image_result.get('fields', []):
                full_text += field.get('inferText', '') + " "

        processed_text = full_text.strip().replace('\n', ' ')
        sentences = kss.split_sentences(processed_text)
        
        ocr_results = [{'id': idx + 1, 'text': sentence.strip()} for idx, sentence in enumerate(sentences) if sentence.strip()]
        
        print(f"OCR 완료: 총 {len(ocr_results)}개의 문장 추출")
        return ocr_results

    except requests.exceptions.RequestException as e:
        print(f"[Naver Cloud OCR 오류] 네트워크 또는 API 요청 오류: {e}")
        if e.response is not None:
             print(f"응답 코드: {e.response.status_code}, 응답 내용: {e.response.text}")
        return []
    except Exception as e:
        print(f"[Naver Cloud OCR 오류] 예측하지 못한 오류 발생: {e}")
        return []

# --------------------------------------------------------------------------
# 🧩 모듈 2: LLM 정보 추출기 (단일 언어용)
# --------------------------------------------------------------------------
def extract_structured_info_with_retry(raw_text: str, max_retries: int = 3, model_name: str = 'mistral:latest') -> dict:
    print(f"\n[ 정보 구조화 시작 (단일 언어) ]")
    # ... (기존 코드와 대부분 동일, 프롬프트만 약간 수정)
    prompt = f"""
    You are an expert business card information extractor.
    From the provided text, extract the required information into a valid JSON format.
    - For missing information, use an empty string "".
    - Return ONLY valid JSON.
    
    Required JSON structure:
    {{
        "name": "", "title": "", "company": "", "phone": "", "email": "", "address": ""
    }}

    --- Text to Analyze ---
    {raw_text}
    """
    # ... (이하 로직은 기존과 동일)
    for attempt in range(max_retries):
        try:
            # ... (Ollama 호출 및 파싱 로직)
            response = ollama.chat(model=model_name, messages=[{'role': 'user', 'content': prompt}], format='json')
            parsed_json = json.loads(response['message']['content'])
            validated_data = validate_and_clean_contact_info(parsed_json)
            print("  ✅ 정보 구조화 성공")
            return validated_data
        except Exception as e:
            print(f"  🚨 오류 발생 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    return get_default_contact_info()

# --------------------------------------------------------------------------
# ✨ Agent 2: 양면 명함 분석 에이전트 (신규 추가) ✨
# --------------------------------------------------------------------------
def two_sided_extract_agent(front_text: str, back_text: str, max_retries: int = 3, model_name: str = 'mistral:latest') -> dict:
    """
    양면 명함의 텍스트를 받아 한글/영문 정보를 분리하여 구조화합니다.
    """
    print(f"\n[ 정보 구조화 시작 (양면 분석) ]")
    
    combined_text = f"--- Front Side (Korean) ---\n{front_text}\n\n--- Back Side (English) ---\n{back_text}"
    
    prompt = f"""
    You are an expert business card extractor for two-sided (Korean/English) cards.
    The provided text contains text from both sides. Extract the information into the following JSON structure.
    - Fill `_ko` fields from Korean text and `_en` fields from English text.
    - For missing information, use an empty string "".
    - `phone` and `email` are usually the same on both sides.
    - Return ONLY valid JSON.

    Required JSON structure:
    {{
        "name_ko": "", "name_en": "",
        "title_ko": "", "title_en": "",
        "company_ko": "", "company_en": "",
        "phone": "", "email": "",
        "address_ko": "", "address_en": ""
    }}

    --- Combined Text to Analyze ---
    {combined_text}
    """

    for attempt in range(max_retries):
        try:
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                format='json'
            )
            parsed_json = json.loads(response['message']['content'])
            # 양면 데이터에 대한 검증 및 정제 함수 호출 (별도 구현)
            validated_data = validate_and_clean_bilingual_info(parsed_json)
            print("  ✅ 양면 정보 구조화 성공")
            return validated_data
        except Exception as e:
            print(f"  🚨 양면 정보 추출 오류 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
    
    return get_default_bilingual_contact_info()

# --------------------------------------------------------------------------
# 🧩 모듈 3: 데이터 검증, 정제 및 포맷팅 (기능 확장)
# --------------------------------------------------------------------------
def get_default_contact_info():
    return {"name": "", "title": "", "company": "", "phone": "", "email": "", "address": ""}

def get_default_bilingual_contact_info():
    return {
        "name_ko": "", "name_en": "", "title_ko": "", "title_en": "",
        "company_ko": "", "company_en": "", "phone": "", "email": "",
        "address_ko": "", "address_en": ""
    }

def validate_and_clean_contact_info(data: dict) -> dict:
    # ... (기존 코드와 동일)
    cleaned_data = get_default_contact_info()
    for key in cleaned_data.keys():
        if key in data and isinstance(data[key], str):
            cleaned_data[key] = data[key].strip()
    if cleaned_data.get('phone'):
        cleaned_data['phone'] = normalize_phone_number(cleaned_data['phone'])
    return cleaned_data

def validate_and_clean_bilingual_info(data: dict) -> dict:
    cleaned_data = get_default_bilingual_contact_info()
    for key in cleaned_data.keys():
        if key in data and isinstance(data[key], str):
            cleaned_data[key] = data[key].strip()
    if cleaned_data.get('phone'):
        cleaned_data['phone'] = normalize_phone_number(cleaned_data['phone'])
    return cleaned_data

def normalize_phone_number(phone: str) -> str:
    # ... (기존 코드와 동일)
    digits = re.sub(r'[^\d]', '', phone)
    if len(digits) == 10: return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 11: return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    return phone

def format_contact_summary(data: dict) -> str:
    if 'name_ko' in data: # 양면 데이터 형식
        name = data.get('name_ko') or data.get('name_en')
        company = data.get('company_ko') or data.get('company_en')
        return f"{name} ({company})" if name else "정보 없음"
    else: # 단면 데이터 형식
        name = data.get('name')
        company = data.get('company')
        return f"{name} ({company})" if name else "정보 없음"

# --------------------------------------------------------------------------
# 🧩 모듈 4: VCF 및 QR 코드 생성 (기능 확장)
# --------------------------------------------------------------------------
def generate_vcf_content(data: dict) -> str:
    """VCF 형식의 연락처 데이터를 생성합니다 (양면 지원)."""
    vcf_lines = ["BEGIN:VCARD", "VERSION:3.0"]
    
    if 'name_ko' in data: # 양면 데이터 처리
        name_ko, name_en = data.get('name_ko'), data.get('name_en')
        title_ko, title_en = data.get('title_ko'), data.get('title_en')
        
        if name_ko or name_en:
            # VCF 표준에 따라 성과 이름을 분리하는 것이 좋지만, 여기서는 편의상 통합
            vcf_lines.append(f"N;CHARSET=UTF-8:{name_ko};{name_en};;;")
            vcf_lines.append(f"FN;CHARSET=UTF-8:{name_ko}{' ' if name_ko and name_en else ''}{name_en}")
        
        if title_ko or title_en:
            vcf_lines.append(f"TITLE;CHARSET=UTF-8:{title_ko}{' / ' if title_ko and title_en else ''}{title_en}")
        
        vcf_lines.append(f"ORG;CHARSET=UTF-8:{data.get('company_ko', '')}")
    
    else: # 단면 데이터 처리
        if data.get('name'):
            vcf_lines.append(f"N:{data['name']};;;;")
            vcf_lines.append(f"FN:{data['name']}")
        if data.get('title'):
            vcf_lines.append(f"TITLE:{data['title']}")
        if data.get('company'):
            vcf_lines.append(f"ORG:{data['company']}")
            
    # 공통 필드
    if data.get('phone'):
        vcf_lines.append(f"TEL;TYPE=WORK,VOICE:{data['phone']}")
    if data.get('email'):
        vcf_lines.append(f"EMAIL;TYPE=WORK:{data['email']}")
    if data.get('address_ko') or data.get('address'):
        address = data.get('address_ko', '') or data.get('address', '')
        vcf_lines.append(f"ADR;TYPE=WORK;CHARSET=UTF-8:;;{address};;;;")

    vcf_lines.append(f"REV:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
    vcf_lines.append("END:VCARD")
    return '\n'.join(vcf_lines)

# --------------------------------------------------------------------------
# 🚀 메인 파이프라인 실행 함수 (기존 단일 처리용)
# --------------------------------------------------------------------------
def run_pipeline(image_path: str, output_dir: str = "output"):
    ocr_results_list = ocr_agent(image_path)
    if not ocr_results_list:
        print("이미지 인식 실패")
        return
    full_ocr_text = ' '.join([item['text'] for item in ocr_results_list])
    structured_data = extract_structured_info_with_retry(full_ocr_text)
    
    # ... (사용자 확인 및 수정 루프는 배치 처리에서 관리)
    
    final_data = structured_data # 여기서는 바로 최종 데이터로 간주
    
    # VCF 및 QR 코드 생성
    # ...
    print("\n🎉 단일 명함 처리 완료!")

# --------------------------------------------------------------------------
# ✨ 다중 파일 처리 및 관리 파이프라인 (신규 추가) ✨
# --------------------------------------------------------------------------
def run_batch_pipeline(image_paths: list[str], output_dir: str = "output"):
    """여러 명함 이미지를 일괄 처리하고, 결과를 관리합니다."""
    print("🚀 다중 명함 처리 파이프라인 시작")
    os.makedirs(output_dir, exist_ok=True)
    
    processed_data = []
    # 1. 모든 파일 자동 처리
    for img_path in image_paths:
        print("-" * 50)
        ocr_results_list = ocr_agent(img_path)
        if not ocr_results_list:
            continue
        full_ocr_text = ' '.join([item['text'] for item in ocr_results_list])
        structured_data = extract_structured_info_with_retry(full_ocr_text)
        processed_data.append({'source': os.path.basename(img_path), 'data': structured_data})

    # 2. 결과 목록 보여주기 및 관리 루프
    filtered_indices = list(range(len(processed_data))) # 초기에는 전체 목록
    
    while True:
        print("\n" + "="*60)
        print("📋 처리 결과 목록 (우측 패널)")
        print("-" * 60)
        
        if not filtered_indices:
            print("  표시할 항목이 없습니다. (필터 결과 없음)")
        else:
            for i, original_idx in enumerate(filtered_indices):
                item = processed_data[original_idx]
                summary = format_contact_summary(item['data'])
                print(f"  {i+1:2d}. [{item['source']}] -> {summary}")

        print("-" * 60)
        print("  [F]ilter: 결과 필터링 | [E]dit: 항목 수정 | [R]eset: 필터 초기화")
        print("  [D]ownload: VCF 다운로드 | [Q]uit: 종료")
        choice = input("선택하세요: ").strip().upper()

        if choice == 'F':
            keyword = input("  🔎 검색할 키워드를 입력하세요 (이름, 회사 등): ").strip()
            if keyword:
                filtered_indices = [
                    i for i, item in enumerate(processed_data)
                    if keyword.lower() in str(item['data'].values()).lower()
                ]
            else:
                 print("  ⚠️ 키워드를 입력해주세요.")
        
        elif choice == 'R':
            filtered_indices = list(range(len(processed_data)))
            print("  🔄 필터가 초기화되었습니다.")

        elif choice == 'E':
            if not filtered_indices:
                 print("  ⚠️ 수정할 항목이 없습니다.")
                 continue
            try:
                target_num = int(input(f"  수정할 항목의 번호를 입력하세요 (1-{len(filtered_indices)}): ").strip())
                if 1 <= target_num <= len(filtered_indices):
                    original_idx = filtered_indices[target_num - 1]
                    # 상세 수정 로직 (기존 edit_all_fields 재활용)
                    # 실제 웹이라면 여기서 팝업/페이지 이동
                    print(f"\n📝 '{processed_data[original_idx]['source']}' 정보 수정")
                    processed_data[original_idx]['data'] = edit_all_fields(processed_data[original_idx]['data'])
                else:
                    print("  ❌ 잘못된 번호입니다.")
            except ValueError:
                print("  ❌ 숫자를 입력해주세요.")

        elif choice == 'D':
            if not filtered_indices:
                 print("  ⚠️ 다운로드할 항목이 없습니다.")
                 continue
            
            # 현재 필터링된 항목들만 다운로드 대상으로 선정
            items_to_download = [processed_data[i] for i in filtered_indices]
            
            # 3. VCF 파일 생성 및 압축
            vcf_files = []
            for item in items_to_download:
                vcf_content = generate_vcf_content(item['data'])
                name = item['data'].get('name_ko') or item['data'].get('name', 'contact')
                safe_name = re.sub(r'[^\w\s-]', '', name).strip()
                vcf_filename = os.path.join(output_dir, f"{safe_name}.vcf")
                with open(vcf_filename, 'w', encoding='utf-8') as f:
                    f.write(vcf_content)
                vcf_files.append(vcf_filename)
                print(f"  ✅ VCF 파일 생성: {vcf_filename}")

            if len(vcf_files) >= 5:
                zip_filename = os.path.join(output_dir, f"contacts_{datetime.now().strftime('%Y%m%d')}.zip")
                print(f"\n  🗜️ 5개 이상이므로 압축 파일을 생성합니다: {zip_filename}")
                with zipfile.ZipFile(zip_filename, 'w') as zf:
                    for file in vcf_files:
                        zf.write(file, os.path.basename(file))
                print("  ✅ 압축 완료!")
            
            print("\n🎉 다운로드 준비가 완료되었습니다!")
            break

        elif choice == 'Q':
            print("프로그램을 종료합니다.")
            break
            
# (edit_all_fields, edit_specific_field 등 사용자 수정 함수는 기존과 동일하게 유지)
def edit_all_fields(data: dict) -> dict:
    """모든 필드를 수정합니다."""
    # ... 기존 코드 ...
    print("\n📝 전체 정보를 다시 입력합니다. (Enter만 누르면 기존 값 유지)")
    
    labels = {}
    if 'name_ko' in data: # 양면 데이터용 레이블
        labels = {
            'name_ko': '이름(한글)', 'name_en': '이름(영문)',
            'title_ko': '직책(한글)', 'title_en': '직책(영문)',
            'company_ko': '회사(한글)', 'company_en': '회사(영문)',
            'phone': '전화번호', 'email': '이메일',
            'address_ko': '주소(한글)', 'address_en': '주소(영문)'
        }
    else: # 단면 데이터용 레이블
        labels = {'name': '이름', 'title': '직책', 'company': '회사', 'phone': '전화번호', 'email': '이메일', 'address': '주소'}

    for key, label in labels.items():
        current_value = data.get(key, '')
        prompt = f"  {label} (현재: {current_value or '없음'}): "
        new_value = input(prompt).strip()
        if new_value:
            data[key] = new_value
    
    print("✅ 전체 정보 수정이 완료되었습니다.")
    return data

# --------------------------------------------------------------------------
# 실행 부분
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # --- 시나리오 1: 여러 개의 단면 명함 일괄 처리 ---
    print("="*60)
    print("🔥 시나리오 1: 여러 개의 단면 명함 일괄 처리")
    print("="*60)
    
    # 처리할 이미지 파일 목록 (sample_data 폴더에 여러 이미지 준비)
    batch_image_paths = [
        "sample_data/real.jpeg",
        "sample_data/card2.png", # 가상의 파일 경로
        "sample_data/card3.png"  # 가상의 파일 경로
    ]
    # 실제 존재하는 파일만 대상으로 처리
    existing_files = [p for p in batch_image_paths if os.path.exists(p)]
    if not existing_files:
        print("⚠️ 처리할 샘플 이미지가 없습니다. 'sample_data' 폴더를 확인해주세요.")
    else:
        run_batch_pipeline(existing_files)

    # --- 시나리오 2: 양면 명함 처리 ---
    print("\n\n" + "="*60)
    print("🔥 시나리오 2: 양면 명함 처리 (앞/뒷면)")
    print("="*60)
    
    front_image_path = "sample_data/real_ko.jpeg" # 한글 명함 경로
    back_image_path = "sample_data/real_en.jpeg" # 영문 명함 경로 (가상)

    if os.path.exists(front_image_path) and os.path.exists(back_image_path):
        # 1. 각 면 OCR
        front_ocr_list = ocr_agent(front_image_path)
        back_ocr_list = ocr_agent(back_image_path)

        if front_ocr_list and back_ocr_list:
            front_text = ' '.join([item['text'] for item in front_ocr_list])
            back_text = ' '.join([item['text'] for item in back_ocr_list])
            
            # 2. 양면 분석 에이전트 호출
            bilingual_data = two_sided_extract_agent(front_text, back_text)
            
            # 3. 결과 확인 및 VCF 생성
            print("\n[ 최종 양면 분석 결과 ]")
            print(json.dumps(bilingual_data, indent=2, ensure_ascii=False))

            vcf_content = generate_vcf_content(bilingual_data)
            output_path = f"output/{bilingual_data.get('name_en', 'bilingual_contact')}.vcf"
            os.makedirs('output', exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(vcf_content)
            print(f"\n✅ 양면 명함 VCF 파일 생성 완료: {output_path}")

    else:
        print("⚠️ 양면 명함 샘플 이미지가 모두 존재하지 않습니다.")

