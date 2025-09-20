# 🚀 Vercel 배포 가이드

## 📁 프로젝트 구조
```
business-card-vercel/
├── app.py                    # Flask 메인 애플리케이션
├── requirements.txt          # Python 의존성
├── vercel.json              # Vercel 배포 설정
├── .env                     # 로컬 환경 변수 (Git 제외)
├── .gitignore               # Git 제외 파일 목록
└── README.md                # 프로젝트 설명
```

## 🛠️ 배포 준비

### 1. GitHub 저장소 생성
```bash
# 프로젝트 폴더 생성
mkdir business-card-vercel
cd business-card-vercel

# Git 초기화
git init

# 파일 생성 (위의 파일들)
# app.py, requirements.txt, vercel.json 등

# .gitignore 생성
echo ".env" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
echo ".DS_Store" >> .gitignore

# Git 커밋
git add .
git commit -m "Initial commit: Flask 명함 처리 시스템"

# GitHub 원격 저장소 연결
git remote add origin https://github.com/your-username/business-card-vercel.git
git branch -M main
git push -u origin main
```

### 2. NAVER CLOVA OCR API 설정 확인
- **Secret Key**: NAVER Cloud Platform에서 발급
- **Invoke URL**: CLOVA OCR 서비스 콘솔에서 확인

### 3. Vercel 계정 및 프로젝트 설정

#### 3.1 Vercel 계정 생성
1. [vercel.com](https://vercel.com) 접속
2. GitHub 계정으로 로그인
3. "Import Project" 선택

#### 3.2 프로젝트 가져오기
1. GitHub 저장소 선택: `business-card-vercel`
2. Framework Preset: **Other** 선택
3. Root Directory: **/** (기본값)
4. Build Command: 비워두기 (Python은 자동)
5. Output Directory: 비워두기
6. Install Command: `pip install -r requirements.txt`

#### 3.3 환경 변수 설정
**Vercel Dashboard > Settings > Environment Variables**
```
NAVER_OCR_SECRET_KEY = your_actual_secret_key
NAVER_OCR_INVOKE_URL = your_actual_invoke_url
```

**중요**: Production, Preview, Development 모두에 적용

### 4. 로컬 테스트 (선택사항)

#### 4.1 로컬 환경 설정
```bash
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정 (.env 파일 생성)
echo "NAVER_OCR_SECRET_KEY=your_secret_key" > .env
echo "NAVER_OCR_INVOKE_URL=your_invoke_url" >> .env
```

#### 4.2 로컬 실행
```bash
python app.py
```
브라우저에서 `http://localhost:5000` 접속

### 5. Vercel CLI 배포 (대안)

#### 5.1 Vercel CLI 설치
```bash
npm install -g vercel
```

#### 5.2 로그인 및 배포
```bash
# Vercel 로그인
vercel login

# 첫 배포
vercel

# 프로덕션 배포
vercel --prod
```

## 🔧 배포 후 확인사항

### 1. 기본 기능 테스트
- [ ] 메인 페이지 로드 확인
- [ ] 파일 업로드 기능
- [ ] OCR 처리 (실제 명함 이미지로 테스트)
- [ ] 정보 수정 기능
- [ ] VCF 파일 다운로드
- [ ] QR 코드 생성

### 2. API 엔드포인트 확인
```bash
# 헬스 체크
curl https://your-project.vercel.app/api/health

# 응답 예시
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "naver_ocr_configured": true
}
```

### 3. 환경 변수 확인
- NAVER OCR 설정이 올바른지 확인
- API 응답에서 `naver_ocr_configured: true` 확인

## 🐛 문제 해결

### 1. 배포 오류
**Build Failed:**
```bash
# Vercel 로그 확인
vercel logs

# 일반적인 해결 방법:
# - requirements.txt 의존성 확인
# - Python 버전 호환성 확인 (3.9-3.11 권장)
# - 파일 경로 및 이름 확인
```

**Runtime Error:**
```bash
# Function 로그 확인
vercel logs --follow

# 일반적인 문제:
# - 환경 변수 미설정
# - API 키 오류
# - 메모리 초과 (이미지 크기 제한)
```

### 2. OCR API 오류
**401 Unauthorized:**
- `NAVER_OCR_SECRET_KEY` 확인
- API 서비스 활성화 상태 확인

**403 Forbidden:**
- 도메인 등록 (필요시)
- 사용량 한도 확인

**500 Internal Server Error:**
- 이미지 형식 확인 (JPG, PNG)
- 이미지 크기 확인 (최대 16MB)

### 3. 성능 최적화
**이미지 크기 제한:**
```python
# app.py에서 크기 제한 조정
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
```

**타임아웃 설정:**
```json
// vercel.json에서 함수 타임아웃 조정
{
  "functions": {
    "app.py": {
      "maxDuration": 60
    }
  }
}
```

## 📊 비용 예상

### Vercel 요금
- **Hobby Plan**: 무료
  - 함수 실행: 월 100GB-시간
  - 대역폭: 월 100GB
  - 적은 사용량에 적합

- **Pro Plan**: $20/월
  - 함수 실행: 월 1,000GB-시간
  - 대역폭: 월 1TB
  - 상업적 사용에 적합

### NAVER CLOVA OCR
- **Document OCR**: 건당 10원
- **Business Card OCR**: 건당 30원
- **무료 크레딧**: 신규 가입시 100,000원

## 🔒 보안 고려사항

### 1. API 키 보안
- 환경 변수로만 관리
- `.env` 파일을 Git에 커밋하지 않음
- Vercel Dashboard에서만 설정

### 2. 파일 업로드 보안
- 파일 크기 제한 (16MB)
- 파일 형식 검증 (이미지만)
- 업로드된 파일은 메모리에서만 처리

### 3. 개인정보 보호
- 이미지는 임시 처리 후 삭제
- 추출된 정보는 서버에 저장하지 않음
- HTTPS 통신으로 데이터 보호

## 🎯 배포 완료 체크리스트

- [ ] GitHub 저장소 생성 및 푸시
- [ ] Vercel 프로젝트 생성
- [ ] 환경 변수 설정 완료
- [ ] 첫 배포 성공
- [ ] 헬스 체크 API 확인
- [ ] 명함 업로드 테스트
- [ ] OCR 처리 테스트
- [ ] VCF 다운로드 테스트
- [ ] QR 코드 생성 테스트
- [ ] 모바일 반응형 확인

## 🌐 최종 결과

배포 완료 후 다음과 같은 URL에서 접근 가능:
- **프로덕션**: `https://your-project.vercel.app`
- **API 헬스체크**: `https://your-project.vercel.app/api/health`

축하합니다! 🎉 이제 전세계 어디서나 접근 가능한 명함 처리 시스템이 완성되었습니다.