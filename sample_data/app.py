from flask import Flask, request, jsonify, render_template_string, send_file
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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# 환경 변수
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')

# HTML 템플릿
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>명함 처리 시스템</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Arial', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }

        .main-container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            gap: 30px;
            align-items: stretch;
        }

        .left-panel {
            flex: 1;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 40px;
            display: flex;
            flex-direction: column;
            min-height: calc(100vh - 40px);
        }

        .right-panel {
            flex: 1;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 40px;
            display: flex;
            flex-direction: column;
            min-height: calc(100vh - 40px);
        }

        .upload-section h1 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 2.2em;
            text-align: center;
        }

        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px;
            margin: 20px 0;
            transition: all 0.3s ease;
            cursor: pointer;
            background: #f8f9ff;
            text-align: center;
        }

        .upload-area:hover {
            background: #f0f2ff;
            border-color: #764ba2;
        }

        .upload-area.dragover {
            background: #e8ecff;
            border-color: #667eea;
            transform: scale(1.02);
        }

        #fileInput {
            display: none;
        }

        .upload-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            border: none;
            padding: 15px 30px;
            border-radius: 25px;
            font-size: 16px;
            cursor: pointer;
            transition: all 0.3s ease;
            margin-top: 20px;
            width: 100%;
        }

        .upload-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(102, 126, 234, 0.3);
        }

        .input-section {
            display: none;
            flex: 1;
            margin-top: 30px;
        }

        .input-section h2 {
            color: #667eea;
            margin-bottom: 20px;
            text-align: center;
        }

        .input-grid {
            display: grid;
            gap: 20px;
            flex: 1;
        }

        .input-group {
            display: flex;
            flex-direction: column;
        }

        .input-group label {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 8px;
            font-size: 14px;
        }

        .input-group input {
            padding: 15px;
            border: 2px solid #e0e7ff;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9ff;
        }

        .input-group input:focus {
            outline: none;
            border-color: #667eea;
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }

        .action-buttons {
            display: flex;
            gap: 15px;
            margin-top: 30px;
        }

        .btn {
            flex: 1;
            padding: 15px 25px;
            border: none;
            border-radius: 25px;
            cursor: pointer;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
        }

        .btn-secondary {
            background: #6c757d;
            color: white;
        }

        .btn-success {
            background: #28a745;
            color: white;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }

        .result-panel {
            display: flex;
            flex-direction: column;
            height: 100%;
        }

        .result-title {
            color: #667eea;
            font-size: 1.8em;
            margin-bottom: 20px;
            text-align: center;
        }

        .preview-section {
            flex: 1;
            display: flex;
            flex-direction: column;
        }

        .info-preview {
            background: #f8f9ff;
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            flex: 1;
        }

        .info-preview h3 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.3em;
        }

        .info-item {
            display: flex;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #e0e7ff;
        }

        .info-item:last-child {
            border-bottom: none;
        }

        .info-label {
            font-weight: bold;
            color: #667eea;
            width: 80px;
            margin-right: 15px;
            font-size: 14px;
        }

        .info-value {
            flex: 1;
            color: #333;
            font-size: 15px;
        }

        .qr-section {
            background: #f8f9ff;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
        }

        .qr-section h3 {
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.3em;
        }

        .qr-code {
            width: 200px;
            height: 200px;
            background: #ddd;
            margin: 0 auto 20px;
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-size: 14px;
        }

        .download-btn {
            background: #28a745;
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            text-decoration: none;
            display: inline-block;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .download-btn:hover {
            background: #219a3c;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(40, 167, 69, 0.3);
        }

        .loading-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            display: none;
            align-items: center;
            justify-content: center;
            z-index: 1000;
            backdrop-filter: blur(10px);
        }

        .loading-container {
            background: white;
            padding: 50px;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 90%;
        }

        .loading-title {
            font-size: 1.8em;
            color: #667eea;
            margin-bottom: 30px;
        }

        .progress-container {
            margin: 30px 0;
        }

        .progress-item {
            display: flex;
            align-items: center;
            margin: 15px 0;
            padding: 15px;
            border-radius: 10px;
            background: #f8f9ff;
            opacity: 0.3;
            transition: all 0.8s ease;
            position: relative;
            overflow: hidden;
        }

        .progress-item.active {
            opacity: 1;
            background: linear-gradient(135deg, #e8f2ff, #f0f8ff);
        }

        .progress-item.completed {
            background: linear-gradient(135deg, #d4edda, #c3e6cb);
            opacity: 1;
        }

        .progress-icon {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #ddd;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 15px;
            transition: all 0.5s ease;
        }

        .progress-item.active .progress-icon {
            background: #667eea;
            color: white;
            animation: pulse 1.5s infinite;
        }

        .progress-item.completed .progress-icon {
            background: #28a745;
            color: white;
        }

        .progress-text {
            font-weight: 500;
            color: #333;
        }

        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }

        .empty-state {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: #666;
            text-align: center;
        }

        .empty-state .icon {
            font-size: 4em;
            margin-bottom: 20px;
            opacity: 0.3;
        }

        .empty-state p {
            font-size: 1.1em;
            line-height: 1.6;
        }

        .error-message {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            border: 1px solid #f5c6cb;
        }

        .success-message {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 10px;
            margin: 10px 0;
            border: 1px solid #c3e6cb;
        }

        @media (max-width: 1024px) {
            .main-container {
                flex-direction: column;
                padding: 15px;
            }
            
            .left-panel, .right-panel {
                min-height: auto;
            }
        }

        @media (max-width: 768px) {
            .main-container {
                padding: 10px;
                gap: 20px;
            }
            
            .left-panel, .right-panel {
                padding: 25px;
            }
            
            .action-buttons {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="main-container">
        <!-- 좌측 패널 -->
        <div class="left-panel">
            <!-- 업로드 섹션 -->
            <div class="upload-section" id="uploadSection">
                <h1>명함 처리 시스템</h1>
                <p style="text-align: center; color: #666; margin-bottom: 20px;">
                    명함 이미지를 업로드하면 자동으로 VCF 파일과 QR 코드를 생성합니다.
                </p>
                
                <div class="upload-area" id="uploadArea">
                    <div>
                        <p style="font-size: 1.2em; margin-bottom: 10px;">📄 명함 이미지를 드래그하거나 클릭하여 업로드</p>
                        <p style="color: #666;">JPG, PNG 파일을 지원합니다</p>
                    </div>
                </div>
                
                <input type="file" id="fileInput" accept="image/*">
                <button class="upload-btn" onclick="document.getElementById('fileInput').click()">
                    파일 선택하기
                </button>
            </div>

            <!-- 입력 섹션 -->
            <div class="input-section" id="inputSection">
                <h2>추출된 정보 수정</h2>
                <div class="input-grid">
                    <div class="input-group">
                        <label for="inputName">이름</label>
                        <input type="text" id="inputName" placeholder="홍길동">
                    </div>
                    <div class="input-group">
                        <label for="inputTitle">직책</label>
                        <input type="text" id="inputTitle" placeholder="개발팀장">
                    </div>
                    <div class="input-group">
                        <label for="inputCompany">회사</label>
                        <input type="text" id="inputCompany" placeholder="테크 컴퍼니">
                    </div>
                    <div class="input-group">
                        <label for="inputPhone">전화번호</label>
                        <input type="text" id="inputPhone" placeholder="010-1234-5678">
                    </div>
                    <div class="input-group">
                        <label for="inputEmail">이메일</label>
                        <input type="email" id="inputEmail" placeholder="hong@techcompany.com">
                    </div>
                    <div class="input-group">
                        <label for="inputAddress">주소</label>
                        <input type="text" id="inputAddress" placeholder="서울시 강남구 테헤란로 123">
                    </div>
                </div>

                <div class="action-buttons">
                    <button class="btn btn-secondary" onclick="resetForm()">다시 업로드</button>
                    <button class="btn btn-success" onclick="generateFiles()">파일 생성</button>
                </div>
            </div>
        </div>

        <!-- 우측 패널 -->
        <div class="right-panel">
            <div class="result-panel">
                <h2 class="result-title">처리 결과</h2>
                
                <!-- 빈 상태 -->
                <div class="empty-state" id="emptyState">
                    <div class="icon">📱</div>
                    <p>명함을 업로드하면<br>여기에 결과가 표시됩니다</p>
                </div>

                <!-- 결과 미리보기 -->
                <div class="preview-section" id="previewSection" style="display: none;">
                    <div class="info-preview">
                        <h3>연락처 정보</h3>
                        <div class="info-item">
                            <span class="info-label">이름:</span>
                            <span class="info-value" id="previewName">-</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">직책:</span>
                            <span class="info-value" id="previewTitle">-</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">회사:</span>
                            <span class="info-value" id="previewCompany">-</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">전화:</span>
                            <span class="info-value" id="previewPhone">-</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">이메일:</span>
                            <span class="info-value" id="previewEmail">-</span>
                        </div>
                        <div class="info-item">
                            <span class="info-label">주소:</span>
                            <span class="info-value" id="previewAddress">-</span>
                        </div>
                    </div>

                    <div class="qr-section">
                        <h3>QR 코드</h3>
                        <div class="qr-code" id="qrCodeDisplay">QR 코드가 여기에 표시됩니다</div>
                        <a href="#" class="download-btn" id="downloadBtn" style="display: none;">
                            VCF 파일 다운로드
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- 로딩 오버레이 -->
    <div class="loading-overlay" id="loadingOverlay">
        <div class="loading-container">
            <h2 class="loading-title">명함 정보 처리 중...</h2>
            <div class="progress-container">
                <div class="progress-item" data-step="1">
                    <div class="progress-icon">1</div>
                    <div class="progress-text">이미지 업로드 및 분석 시작</div>
                </div>
                <div class="progress-item" data-step="2">
                    <div class="progress-icon">2</div>
                    <div class="progress-text">NAVER CLOVA OCR 처리 중</div>
                </div>
                <div class="progress-item" data-step="3">
                    <div class="progress-icon">3</div>
                    <div class="progress-text">연락처 정보 구조화</div>
                </div>
                <div class="progress-item" data-step="4">
                    <div class="progress-icon">4</div>
                    <div class="progress-text">VCF 파일 형식 변환</div>
                </div>
                <div class="progress-item" data-step="5">
                    <div class="progress-icon">5</div>
                    <div class="progress-text">QR 코드 생성 중</div>
                </div>
                <div class="progress-item" data-step="6">
                    <div class="progress-icon">6</div>
                    <div class="progress-text">최종 검토 및 완료</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // 전역 변수
        let currentData = null;

        // 파일 업로드 처리
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');

        uploadArea.addEventListener('click', () => fileInput.click());

        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                processFile(files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                processFile(e.target.files[0]);
            }
        });

        // 입력 필드 실시간 업데이트
        const inputFields = ['Name', 'Title', 'Company', 'Phone', 'Email', 'Address'];
        inputFields.forEach(field => {
            document.getElementById(`input${field}`).addEventListener('input', updatePreview);
        });

        function updatePreview() {
            inputFields.forEach(field => {
                const inputValue = document.getElementById(`input${field}`).value;
                document.getElementById(`preview${field}`).textContent = inputValue || '-';
            });
        }

        // 파일 처리
        async function processFile(file) {
            if (!file.type.startsWith('image/')) {
                showError('이미지 파일만 업로드 가능합니다.');
                return;
            }

            if (file.size > 16 * 1024 * 1024) {
                showError('파일 크기는 16MB를 초과할 수 없습니다.');
                return;
            }

            showLoading();

            try {
                const formData = new FormData();
                formData.append('image', file);

                const response = await fetch('/api/process-business-card', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();

                if (result.success) {
                    hideLoading();
                    showResult(result.contactInfo);
                    currentData = result.contactInfo;
                } else {
                    throw new Error(result.error || '처리 실패');
                }

            } catch (error) {
                hideLoading();
                showError('처리 중 오류가 발생했습니다: ' + error.message);
            }
        }

        // 로딩 화면 표시
        function showLoading() {
            document.getElementById('loadingOverlay').style.display = 'flex';
            
            const steps = [1, 2, 3, 4, 5, 6];
            let currentStep = 0;

            function processNextStep() {
                if (currentStep < steps.length) {
                    const stepElement = document.querySelector(`[data-step="${steps[currentStep]}"]`);
                    stepElement.classList.add('active');
                    
                    setTimeout(() => {
                        stepElement.classList.remove('active');
                        stepElement.classList.add('completed');
                        stepElement.querySelector('.progress-icon').innerHTML = '✓';
                        
                        currentStep++;
                        if (currentStep < steps.length) {
                            processNextStep();
                        }
                    }, 2000);
                }
            }

            processNextStep();
        }

        // 로딩 화면 숨기기
        function hideLoading() {
            document.getElementById('loadingOverlay').style.display = 'none';
            
            // 진행 상태 초기화
            const steps = document.querySelectorAll('.progress-item');
            steps.forEach((step, index) => {
                step.classList.remove('active', 'completed');
                step.querySelector('.progress-icon').innerHTML = index + 1;
            });
        }

        // 결과 표시
        function showResult(contactInfo) {
            document.getElementById('uploadSection').style.display = 'none';
            document.getElementById('inputSection').style.display = 'flex';
            
            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('previewSection').style.display = 'flex';

            // 입력 필드 채우기
            inputFields.forEach(field => {
                const key = field.toLowerCase();
                const value = contactInfo[key] || '';
                document.getElementById(`input${field}`).value = value;
            });

            updatePreview();
        }

        // 폼 리셋
        function resetForm() {
            document.getElementById('uploadSection').style.display = 'block';
            document.getElementById('inputSection').style.display = 'none';
            
            document.getElementById('emptyState').style.display = 'flex';
            document.getElementById('previewSection').style.display = 'none';
            document.getElementById('downloadBtn').style.display = 'none';

            inputFields.forEach(field => {
                document.getElementById(`input${field}`).value = '';
                document.getElementById(`preview${field}`).textContent = '-';
            });

            document.getElementById('fileInput').value = '';
            currentData = null;
        }

        // 파일 생성
        async function generateFiles() {
            const contactData = {
                name: document.getElementById('inputName').value,
                title: document.getElementById('inputTitle').value,
                company: document.getElementById('inputCompany').value,
                phone: document.getElementById('inputPhone').value,
                email: document.getElementById('inputEmail').value,
                address: document.getElementById('inputAddress').value
            };

            if (!contactData.name) {
                showError('이름은 필수 입력 항목입니다.');
                return;
            }

            try {
                const response = await fetch('/api/generate-files', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ contactData })
                });

                const result = await response.json();

                if (result.success) {
                    // QR 코드 표시
                    document.getElementById('qrCodeDisplay').innerHTML = 
                        `<img src="data:image/png;base64,${result.qrCode}" alt="QR Code" style="max-width: 100%; border-radius: 10px;">`;
                    
                    // VCF 다운로드 링크 설정
                    const downloadBtn = document.getElementById('downloadBtn');
                    downloadBtn.href = `/api/download-vcf?data=${encodeURIComponent(JSON.stringify(contactData))}`;
                    downloadBtn.style.display = 'inline-block';
                    
                    showSuccess('파일이 생성되었습니다!');
                } else {
                    throw new Error(result.error);
                }
            } catch (error) {
                showError('파일 생성 중 오류가 발생했습니다: ' + error.message);
            }
        }

        // 에러 메시지 표시
        function showError(message) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error-message';
            errorDiv.textContent = message;
            
            document.body.insertBefore(errorDiv, document.body.firstChild);
            
            setTimeout(() => {
                errorDiv.remove();
            }, 5000);
        }

        // 성공 메시지 표시
        function showSuccess(message) {
            const successDiv = document.createElement('div');
            successDiv.className = 'success-message';
            successDiv.textContent = message;
            
            document.body.insertBefore(successDiv, document.body.firstChild);
            
            setTimeout(() => {
                successDiv.remove();
            }, 5000);
        }
    </script>
</body>
</html>
'''

# OCR 처리 함수들 (기존 Python 코드에서 가져옴)
def call_naver_ocr(image_data):
    """NAVER CLOVA OCR API 호출"""
    if not NAVER_OCR_SECRET_KEY or not NAVER_OCR_INVOKE_URL:
        raise Exception('NAVER CLOVA OCR 환경 변수가 설정되지 않았습니다.')
    
    request_id = f"OCR-{int(time.time() * 1000)}"
    
    request_body = {
        'version': 'V2',
        'requestId': request_id,
        'timestamp': int(time.time() * 1000),
        'lang': 'ko',
        'images': [
            {
                'format': 'JPG',
                'name': 'business_card',
                'data': image_data
            }
        ],
        'enableTableDetection': False
    }
    
    headers = {
        'Content-Type': 'application/json',
        'X-OCR-Secret': NAVER_OCR_SECRET_KEY
    }
    
    response = requests.post(
        NAVER_OCR_INVOKE_URL,
        headers=headers,
        data=json.dumps(request_body),
        timeout=30
    )
    response.raise_for_status()
    
    return response.json()

def extract_contact_info(ocr_result):
    """OCR 결과에서 연락처 정보 추출"""
    default_info = {
        'name': '',
        'title': '',
        'company': '',
        'phone': '',
        'email': '',
        'address': ''
    }

    if not ocr_result.get('images') or not ocr_result['images'][0].get('fields'):
        return default_info

    fields = ocr_result['images'][0]['fields']
    texts = [field.get('inferText', '').strip() for field in fields if field.get('inferText')]
    full_text = ' '.join(texts)

    return {
        'name': extract_name(texts),
        'title': extract_title(texts),
        'company': extract_company(texts),
        'phone': extract_phone(full_text),
        'email': extract_email(full_text),
        'address': extract_address(texts)
    }

def extract_name(texts):
    """이름 추출"""
    korean_name_pattern = re.compile(r'^[가-힣]{2,4}$')
    english_name_pattern = re.compile(r'^[A-Za-z]{2,}\s+[A-Za-z]{2,}$')
    
    for text in texts:
        text = text.strip()
        if korean_name_pattern.match(text) or english_name_pattern.match(text):
            return text
    
    return texts[0] if texts else ''

def extract_title(texts):
    """직책 추출"""
    title_keywords = [
        '대표', '사장', '부사장', '전무', '상무', '이사', '부장', '차장', '과장', '팀장',
        '매니저', '주임', '대리', '사원', '연구원', '개발자', '엔지니어', '디자이너',
        'CEO', 'CTO', 'CIO', 'CFO', 'COO', 'President', 'Director', 'Manager',
        'Lead', 'Senior', 'Junior', 'Developer', 'Engineer', 'Designer'
    ]
    
    for text in texts:
        text = text.strip()
        if any(keyword in text for keyword in title_keywords):
            return text
    
    return ''

def extract_company(texts):
    """회사명 추출"""
    company_keywords = [
        '주식회사', '(주)', '㈜', '유한회사', '(유)', '법인', '기업', '그룹', '컴퍼니',
        'Company', 'Corp', 'Corporation', 'Inc', 'Ltd', 'Limited', 'LLC'
    ]
    
    for text in texts:
        text = text.strip()
        if any(keyword in text for keyword in company_keywords):
            return text
    
    # 가장 긴 텍스트를 회사명으로 추정 (이메일, 전화번호 제외)
    filtered_texts = [t for t in texts if '@' not in t and not re.search(r'\d{2,3}-\d{3,4}-\d{4}', t)]
    if filtered_texts:
        return max(filtered_texts, key=len)
    
    return ''

def extract_phone(text):
    """전화번호 추출"""
    phone_patterns = [
        r'(?:010|011|016|017|018|019)[-\s]?\d{3,4}[-\s]?\d{4}',
        r'(?:02|0[3-6][1-4])[-\s]?\d{3,4}[-\s]?\d{4}',
        r'\d{2,3}[-\s]?\d{3,4}[-\s]?\d{4}'
    ]
    
    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            return normalize_phone_number(match.group())
    
    return ''

def normalize_phone_number(phone):
    """전화번호 정규화"""
    digits = re.sub(r'[^\d]', '', phone)
    
    if len(digits) == 10:
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    elif len(digits) == 11:
        return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
    
    return phone

def extract_email(text):
    """이메일 추출"""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group().lower() if match else ''

def extract_address(texts):
    """주소 추출"""
    address_keywords = ['시', '구', '군', '동', '로', '길', '번지', '층', '호', '대로']
    
    for text in texts:
        text = text.strip()
        if len(text) > 10 and any(keyword in text for keyword in address_keywords):
            return text
    
    return ''

def generate_vcf_content(data):
    """VCF 파일 내용 생성"""
    vcf_lines = [
        "BEGIN:VCARD",
        "VERSION:3.0"
    ]
    
    if data.get('name'):
        vcf_lines.append(f"FN:{data['name']}")
        vcf_lines.append(f"N:{data['name']};;;;")
    
    if data.get('company'):
        vcf_lines.append(f"ORG:{data['company']}")
    
    if data.get('title'):
        vcf_lines.append(f"TITLE:{data['title']}")
    
    if data.get('phone'):
        vcf_lines.append(f"TEL;TYPE=WORK,VOICE:{data['phone']}")
    
    if data.get('email'):
        vcf_lines.append(f"EMAIL;TYPE=WORK:{data['email']}")
    
    if data.get('address'):
        vcf_lines.append(f"ADR;TYPE=WORK:;;{data['address']};;;;")
    
    vcf_lines.append(f"REV:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
    vcf_lines.append("END:VCARD")
    
    return '\n'.join(vcf_lines)

def generate_qr_code(vcf_content):
    """QR 코드 생성"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(vcf_content)
    qr.make(fit=True)
    
    qr_image = qr.make_image(fill_color="black", back_color="white")
    
    # 이미지를 바이트로 변환
    img_buffer = io.BytesIO()
    qr_image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Base64로 인코딩
    import base64
    qr_base64 = base64.b64encode(img_buffer.getvalue()).decode()
    
    return qr_base64

# Flask 라우트들
@app.route('/')
def index():
    """메인 페이지"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/process-business-card', methods=['POST'])
def process_business_card():
    """명함 처리 API"""
    try:
        if 'image' not in request.files:
            return jsonify({'success': False, 'error': '이미지 파일이 필요합니다.'})
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'error': '파일이 선택되지 않았습니다.'})
        
        if not file.content_type.startswith('image/'):
            return jsonify({'success': False, 'error': '이미지 파일만 업로드 가능합니다.'})
        
        # 이미지를 Base64로 인코딩
        image_data = base64.b64encode(file.read()).decode('utf-8')
        
        # NAVER CLOVA OCR 호출
        ocr_result = call_naver_ocr(image_data)
        
        # 연락처 정보 추출
        contact_info = extract_contact_info(ocr_result)
        
        return jsonify({
            'success': True,
            'contactInfo': contact_info,
            'extractedText': ' '.join([field.get('inferText', '') for field in ocr_result.get('images', [{}])[0].get('fields', [])]),
            'confidence': calculate_confidence(ocr_result)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/generate-files', methods=['POST'])
def generate_files():
    """VCF 파일과 QR 코드 생성 API"""
    try:
        data = request.get_json()
        contact_data = data.get('contactData', {})
        
        if not contact_data.get('name'):
            return jsonify({'success': False, 'error': '이름은 필수 입력 항목입니다.'})
        
        # VCF 내용 생성
        vcf_content = generate_vcf_content(contact_data)
        
        # QR 코드 생성
        qr_base64 = generate_qr_code(vcf_content)
        
        return jsonify({
            'success': True,
            'vcfContent': vcf_content,
            'qrCode': qr_base64
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download-vcf')
def download_vcf():
    """VCF 파일 다운로드"""
    try:
        data_param = request.args.get('data')
        if not data_param:
            return "데이터가 없습니다.", 400
        
        contact_data = json.loads(data_param)
        vcf_content = generate_vcf_content(contact_data)
        
        # 임시 파일 생성
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.vcf', delete=False, encoding='utf-8')
        temp_file.write(vcf_content)
        temp_file.close()
        
        filename = f"{contact_data.get('name', 'contact')}.vcf"
        
        return send_file(
            temp_file.name,
            as_attachment=True,
            download_name=filename,
            mimetype='text/vcard'
        )
        
    except Exception as e:
        return f"파일 생성 오류: {str(e)}", 500

def calculate_confidence(ocr_result):
    """OCR 신뢰도 계산"""
    if not ocr_result.get('images') or not ocr_result['images'][0].get('fields'):
        return 0
    
    fields = ocr_result['images'][0]['fields']
    if not fields:
        return 0
    
    total_confidence = sum(field.get('inferConfidence', 0) for field in fields)
    return total_confidence / len(fields)

# 환경 변수 확인
@app.route('/api/health')
def health_check():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'naver_ocr_configured': bool(NAVER_OCR_SECRET_KEY and NAVER_OCR_INVOKE_URL)
    })

if __name__ == '__main__':
    app.run(debug=True)