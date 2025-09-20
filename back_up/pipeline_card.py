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

# --- .env 파일에서 환경 변수 로드 ---
import dotenv
dotenv.load_dotenv()

# NAVER CLOVA OCR 환경 변수
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')

# --------------------------------------------------------------------------
# 🤖 Agent 1: OCR Agent (Naver Cloud OCR 사용)
# --------------------------------------------------------------------------
def ocr_agent(image_path: str) -> list[dict]:
    print(f"\n[ OCR Agent using Naver Cloud OCR ] '{os.path.basename(image_path)}' 이미지 처리 시작...")
    
    # 1. 요청에 필요한 정보 구성
    # requests_body는 message 파트에 JSON 형식으로 들어갈 내용
    request_body = {
        'version': 'V2',
        'requestId': 'NCP-OCR-ID-' + str(int(time.time() * 1000)), 
        'timestamp': int(time.time() * 1000),
        'lang': 'ko', 
        'images': [
            {
                'format': os.path.splitext(image_path)[1][1:].upper(), # 이미지 확장자를 대문자로 (PNG, JPG)
                'name': os.path.basename(image_path),
                # 'data' 또는 'url' 필드는 multipart/form-data 전송 시 여기서는 포함하지 않습니다.
            }
        ]
    }
    
    # 2. headers 구성: Secret Key는 여기에 넣습니다.
    # Content-Type은 files가 처리하므로 여기서는 명시하지 않습니다.
    headers = {
        'X-OCR-Secret': NAVER_OCR_SECRET_KEY,
        # 'Content-Type': 'multipart/form-data' # requests가 자동으로 설정하므로 제거
    }

    try:
        # 3. 파일 및 JSON 메시지 준비
        # 'file' 파트와 'message' 파트를 정확히 구성
        with open(image_path, 'rb') as img_file:
            files = {
                'file': (os.path.basename(image_path), img_file, 'image/' + os.path.splitext(image_path)[1][1:].lower()), # ('파일명', 파일 객체, 'Content-Type')
                'message': (None, json.dumps(request_body).encode('UTF-8'), 'application/json') # ('필드명', JSON 데이터, 'Content-Type')
            }
            
            # 4. API 호출
            # headers=headers 로 Secret Key를 정확히 전달
            response = requests.post(NAVER_OCR_INVOKE_URL, headers=headers, files=files)
            response.raise_for_status() # HTTP 오류가 발생하면 예외 발생

        # 5. 응답 파싱 및 텍스트 추출 (이하 동일)
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
    except json.JSONDecodeError:
        print(f"[Naver Cloud OCR 오류] API 응답이 유효한 JSON 형식이 아닙니다. 원본 응답:\n{response.text}")
        return []
    except Exception as e:
        print(f"[Naver Cloud OCR 오류] 예측하지 못한 오류 발생: {e}")
        return []

# --------------------------------------------------------------------------
# 🧩 모듈 2: LLM 정보 추출기 (재시도 기능 포함)
# --------------------------------------------------------------------------
def extract_structured_info_with_retry(raw_text: str, max_retries: int = 3, model_name: str = 'mistral:latest') -> dict:
    """
    LLM을 호출하여 텍스트를 구조화하고, 실패 시 재시도합니다.
    """
    print(f"\n[ 정보 구조화 시작 ] (최대 {max_retries}회 시도)")
    
    if not raw_text.strip():
        print("  ⚠️ 입력 텍스트가 비어있습니다.")
        return get_default_contact_info()
    
    prompt = f"""
    You are an expert business card information extractor for Korean and English business cards.
    From the provided text, identify and extract the required information into a valid JSON format.
    
    Instructions:
    1. Extract ONLY the information that is clearly present in the text
    2. For missing information, use empty string ""
    3. Phone numbers should be in Korean format (010-1234-5678)
    4. Names should be properly formatted (Korean: 홍길동, English: John Smith)
    5. Return ONLY valid JSON, no explanations
    f
    Required JSON structure:
    {{
        "name": "",
        "title": "",
        "company": "",
        "phone": "",
        "email": "",
        "address": ""
    }}

    --- Text to Analyze ---
    {raw_text}
    """

    for attempt in range(max_retries):
        try:
            print(f"  - 시도 {attempt + 1}/{max_retries}...")
            
            # Ollama 모델 확인
            available_models = ollama.list()
            model_names = [model['name'] for model in available_models['models']]
            
            if model_name not in model_names:
                print(f"  ⚠️ 모델 '{model_name}'이 없습니다. 사용 가능한 모델: {model_names}")
                if model_names:
                    model_name = model_names[0]
                    print(f"  🔄 '{model_name}' 모델로 변경합니다.")
                else:
                    raise Exception("사용 가능한 Ollama 모델이 없습니다.")
            
            response = ollama.chat(
                model=model_name,
                messages=[{'role': 'user', 'content': prompt}],
                format='json',
                options={
                    'temperature': 0.1,
                    'top_p': 0.9,
                    'num_predict': 512
                }
            )
            
            parsed_json = response['message']['content']
            
            # 응답이 문자열인 경우 JSON 파싱
            if isinstance(parsed_json, str):
                # JSON 블록 추출 (```json...``` 형태일 수 있음)
                json_match = re.search(r'```json\s*(.*?)\s*```', parsed_json, re.DOTALL)
                if json_match:
                    parsed_json = json_match.group(1)
                
                parsed_json = json.loads(parsed_json)
            
            # 결과 검증 및 정제
            validated_data = validate_and_clean_contact_info(parsed_json)
            
            print("  ✅ 정보 구조화 성공")
            print(f"  📋 추출된 정보: {format_contact_info_summary(validated_data)}")
            
            return validated_data
            
        except json.JSONDecodeError as e:
            print(f"  🚨 JSON 파싱 오류: {e}")
            if attempt < max_retries - 1:
                print("  🔄 재시도합니다...")
                time.sleep(2)
        except Exception as e:
            print(f"  🚨 오류 발생: {e}")
            if attempt < max_retries - 1:
                print("  🔄 재시도합니다...")
                time.sleep(2)
            else:
                print("  🚨 최종 실패: 최대 재시도 횟수를 초과했습니다.")
    
    # 모든 시도 실패시 기본값 반환
    print("  ⚠️ 자동 추출 실패, 수동 정규식 추출을 시도합니다...")
    return manual_extract_contact_info(raw_text)

def get_default_contact_info() -> dict:
    """기본 연락처 정보 구조를 반환합니다."""
    return {
        "name": "",
        "title": "",
        "company": "",
        "phone": "",
        "email": "",
        "address": ""
    }

def validate_and_clean_contact_info(data: dict) -> dict:
    """연락처 정보를 검증하고 정제합니다."""
    cleaned_data = get_default_contact_info()
    
    for key in cleaned_data.keys():
        if key in data and isinstance(data[key], str):
            cleaned_data[key] = data[key].strip()
    
    # 전화번호 정규화
    if cleaned_data['phone']:
        cleaned_data['phone'] = normalize_phone_number(cleaned_data['phone'])
    
    # 이메일 소문자 변환
    if cleaned_data['email']:
        cleaned_data['email'] = cleaned_data['email'].lower()
    
    return cleaned_data

def normalize_phone_number(phone: str) -> str:
    """전화번호를 한국 표준 형식으로 정규화합니다."""
    # 숫자만 추출
    digits = re.sub(r'[^\d]', '', phone)
    
    # 길이별 형식화
    if len(digits) == 10:  # 02-xxxx-xxxx
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    elif len(digits) == 11:  # 010-xxxx-xxxx
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    else:
        return phone  # 원본 반환

def manual_extract_contact_info(text: str) -> dict:
    """정규식을 사용한 수동 정보 추출 (LLM 실패시 백업)"""
    info = get_default_contact_info()
    
    # 전화번호 추출
    phone_patterns = [
        r'(?:010|011|016|017|018|019)[-\s]?\d{3,4}[-\s]?\d{4}',
        r'(?:02|0[3-6][1-4])[-\s]?\d{3,4}[-\s]?\d{4}'
    ]
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            info['phone'] = normalize_phone_number(match.group())
            break
    
    # 이메일 추출
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    if email_match:
        info['email'] = email_match.group().lower()
    
    # 이름 추출 (한글 2-4자)
    name_match = re.search(r'[가-힣]{2,4}', text)
    if name_match:
        info['name'] = name_match.group()
    
    return info

def format_contact_info_summary(data: dict) -> str:
    """연락처 정보 요약을 포맷팅합니다."""
    summary_parts = []
    for key, value in data.items():
        if value:
            summary_parts.append(f"{key}: {value}")
    return ", ".join(summary_parts) if summary_parts else "정보 없음"

# --------------------------------------------------------------------------
# 🧩 모듈 3: 사용자 확인 및 수정 루프
# --------------------------------------------------------------------------
def user_confirmation_and_edit_loop(data: dict) -> dict:
    """
    사용자에게 최종 결과를 보여주고, 수정 또는 다운로드를 선택하게 합니다.
    """
    print("\n[ 최종 확인 및 수정 ]")
    
    while True:
        print("\n" + "="*50)
        print("📋 최종 인식 결과")
        print("="*50)
        
        for idx, (key, value) in enumerate(data.items(), 1):
            korean_labels = {
                'name': '이름',
                'title': '직책',
                'company': '회사',
                'phone': '전화번호',
                'email': '이메일',
                'address': '주소'
            }
            label = korean_labels.get(key, key)
            print(f"  {idx}. {label:<8}: {value or '(정보 없음)'}")
        
        print("="*50)
        print("\n선택사항:")
        print("  1. 다운로드 - 현재 정보로 VCF 파일과 QR 코드 생성")
        print("  2. 수정 - 특정 항목 수정")
        print("  3. 전체 수정 - 모든 항목 다시 입력")
        print("  4. 종료 - 프로그램 종료")
        
        choice = input("\n선택하세요 (1-4): ").strip()
        
        if choice == '1' or choice == '다운로드':
            return data
        elif choice == '2' or choice == '수정':
            data = edit_specific_field(data)
        elif choice == '3' or choice == '전체수정':
            data = edit_all_fields(data)
        elif choice == '4' or choice == '종료':
            print("프로그램을 종료합니다.")
            exit(0)
        else:
            print("❌ 잘못된 선택입니다. 1-4 중에서 선택해주세요.")

def edit_specific_field(data: dict) -> dict:
    """특정 필드를 수정합니다."""
    korean_labels = {
        'name': '이름',
        'title': '직책', 
        'company': '회사',
        'phone': '전화번호',
        'email': '이메일',
        'address': '주소'
    }
    
    print("\n수정할 항목을 선택하세요:")
    for idx, (key, label) in enumerate(korean_labels.items(), 1):
        current_value = data.get(key, '')
        print(f"  {idx}. {label} (현재: {current_value or '정보 없음'})")
    
    try:
        choice = int(input("\n항목 번호 (1-6): ").strip())
        if 1 <= choice <= 6:
            key = list(korean_labels.keys())[choice - 1]
            label = korean_labels[key]
            
            current_value = data.get(key, '')
            new_value = input(f"\n{label}의 새로운 값을 입력하세요 (현재: {current_value}): ").strip()
            
            if new_value:
                if key == 'phone':
                    new_value = normalize_phone_number(new_value)
                elif key == 'email':
                    new_value = new_value.lower()
                
                data[key] = new_value
                print(f"✅ {label}이(가) '{new_value}'로 수정되었습니다.")
            else:
                print("❌ 빈 값입니다. 수정을 취소합니다.")
        else:
            print("❌ 잘못된 번호입니다.")
    except ValueError:
        print("❌ 숫자를 입력해주세요.")
    
    return data

def edit_all_fields(data: dict) -> dict:
    """모든 필드를 수정합니다."""
    korean_labels = {
        'name': '이름',
        'title': '직책',
        'company': '회사', 
        'phone': '전화번호',
        'email': '이메일',
        'address': '주소'
    }
    
    print("\n📝 전체 정보를 다시 입력합니다. (Enter만 누르면 기존 값 유지)")
    
    for key, label in korean_labels.items():
        current_value = data.get(key, '')
        prompt = f"{label} (현재: {current_value or '없음'}): "
        new_value = input(prompt).strip()
        
        if new_value:
            if key == 'phone':
                new_value = normalize_phone_number(new_value)
            elif key == 'email':
                new_value = new_value.lower()
            data[key] = new_value
    
    print("✅ 전체 정보 수정이 완료되었습니다.")
    return data

# --------------------------------------------------------------------------
# 🧩 모듈 4: VCF 및 QR 코드 생성
# --------------------------------------------------------------------------
def generate_vcf_and_qr(data: dict, output_dir: str = "output") -> tuple:
    """VCF 파일과 QR 코드를 생성합니다."""
    print(f"\n[ VCF 및 QR 코드 생성 ]")
    
    # 출력 디렉토리 생성
    os.makedirs(output_dir, exist_ok=True)
    
    # 파일명 생성 (이름 기반, 없으면 타임스탬프)
    name = data.get('name', '').strip()
    if name:
        safe_name = re.sub(r'[^\w\s-]', '', name).strip()
        safe_name = re.sub(r'[-\s]+', '_', safe_name)
    else:
        safe_name = f"contact_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # VCF 파일 생성
    vcf_content = generate_vcf_content(data)
    vcf_filename = os.path.join(output_dir, f"{safe_name}.vcf")
    
    try:
        with open(vcf_filename, 'w', encoding='utf-8') as f:
            f.write(vcf_content)
        print(f"  ✅ VCF 파일 생성: {vcf_filename}")
    except Exception as e:
        print(f"  ❌ VCF 파일 생성 실패: {e}")
        vcf_filename = None
    
    # QR 코드 생성
    qr_filename = os.path.join(output_dir, f"{safe_name}_qr.png")
    
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(vcf_content)
        qr.make(fit=True)
        
        qr_image = qr.make_image(fill_color="black", back_color="white")
        qr_image.save(qr_filename)
        print(f"  ✅ QR 코드 생성: {qr_filename}")
    except Exception as e:
        print(f"  ❌ QR 코드 생성 실패: {e}")
        qr_filename = None
    
    return vcf_filename, qr_filename

def generate_vcf_content(data: dict) -> str:
    """VCF 형식의 연락처 데이터를 생성합니다."""
    vcf_lines = [
        "BEGIN:VCARD",
        "VERSION:3.0"
    ]
    
    # 이름 (필수)
    if data.get('name'):
        vcf_lines.append(f"FN:{data['name']}")
        vcf_lines.append(f"N:{data['name']};;;;")
    
    # 회사 및 직책
    if data.get('company'):
        vcf_lines.append(f"ORG:{data['company']}")
    
    if data.get('title'):
        vcf_lines.append(f"TITLE:{data['title']}")
    
    # 전화번호
    if data.get('phone'):
        vcf_lines.append(f"TEL;TYPE=WORK,VOICE:{data['phone']}")
    
    # 이메일
    if data.get('email'):
        vcf_lines.append(f"EMAIL;TYPE=WORK:{data['email']}")
    
    # 주소
    if data.get('address'):
        vcf_lines.append(f"ADR;TYPE=WORK:;;{data['address']};;;;")
    
    # 생성 시간
    vcf_lines.append(f"REV:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
    
    vcf_lines.append("END:VCARD")
    
    return '\n'.join(vcf_lines)

# --------------------------------------------------------------------------
# 🚀 메인 파이프라인 실행 함수
# --------------------------------------------------------------------------
def run_pipeline(image_path: str, output_dir: str = "output"):
    """전체 명함 처리 파이프라인을 실행합니다."""
    print("🚀 명함 처리 파이프라인 시작")
    print(f"📁 입력 이미지: {image_path}")
    print(f"📁 출력 디렉토리: {output_dir}")
    
    # 1. OCR 처리
    ocr_results_list = ocr_agent(image_path)
    if not ocr_results_list:
        print("\n❌ 파이프라인 중단: 이미지 인식에 실패했습니다.")
        print("💡 해결 방법:")
        print("  - 이미지가 선명한지 확인하세요")
        print("  - 조명이 충분한지 확인하세요") 
        print("  - 지원되는 형식(JPG, PNG)인지 확인하세요")
        print("  - NAVER CLOVA OCR 환경 변수가 올바른지 확인하세요")
        return False

    # 2. LLM으로 정보 구조화
    # OCR 결과(리스트)를 하나의 문자열로 합칩니다.
    full_ocr_text = ' '.join([item['text'] for item in ocr_results_list])
    
    structured_data = extract_structured_info_with_retry(full_ocr_text, model_name='mistral:latest')
    if not structured_data:
        print("\n❌ 파이프라인 중단: 텍스트 분석에 실패했습니다.")
        print("💡 해결 방법:")
        print("  - Ollama가 실행 중인지 확인하세요")
        print("  - 모델이 설치되어 있는지 확인하세요 (ollama pull mistral)")
        return False

    # 3. 사용자 최종 확인 및 수정
    final_data = user_confirmation_and_edit_loop(structured_data)

    # 4. VCF 및 QR 코드 생성
    vcf_file, qr_file = generate_vcf_and_qr(final_data, output_dir)
    
    # 5. 완료 메시지
    print("\n🎉 명함 처리 파이프라인이 성공적으로 완료되었습니다!")
    print("\n📋 최종 결과:")
    print(f"  - VCF 파일: {vcf_file}")
    print(f"  - QR 코드: {qr_file}")
    print(f"  - 출력 디렉토리: {os.path.abspath(output_dir)}")
    
    return True

# --------------------------------------------------------------------------
# 실행 부분
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # 환경 변수 확인
    if not NAVER_OCR_SECRET_KEY or not NAVER_OCR_INVOKE_URL:
        print("❌ 환경 변수 설정이 필요합니다!")
        print("\n.env 파일에 다음 내용을 추가하세요:")
        print("NAVER_OCR_SECRET_KEY=your_secret_key")
        print("NAVER_OCR_INVOKE_URL=your_invoke_url")
        exit(1)
    
    # 분석할 명함 이미지 경로를 여기에 입력하세요.
    target_image_path = "sample_data/real.jpeg"  # 실제 이미지 경로로 변경하세요
    
    # 이미지 파일 존재 확인
    if not os.path.exists(target_image_path):
        print(f"❌ 이미지 파일을 찾을 수 없습니다: {target_image_path}")
        print("💡 올바른 이미지 경로를 설정하고 다시 실행하세요.")
        exit(1)
    
    # 파이프라인 실행
    success = run_pipeline(target_image_path)
    
    if success:
        print("\n✅ 프로그램이 정상적으로 완료되었습니다.")
    else:
        print("\n❌ 프로그램 실행 중 오류가 발생했습니다.")
        exit(1)