# 🚀 명함 처리 시스템 (Vercel 배포)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https://github.com/your-username/business-card-vercel)

실시간으로 명함 이미지를 업로드하여 연락처 정보를 추출하고 VCF 파일과 QR 코드를 생성하는 웹 애플리케이션입니다.

## ✨ 주요 기능

- 📱 **드래그 앤 드롭** 파일 업로드
- 🔍 **NAVER CLOVA OCR** 명함 텍스트 추출
- ✏️ **실시간 편집** 추출된 정보 수정
- 📄 **VCF 파일** 자동 생성 및 다운로드
- 📱 **QR 코드** 생성 및 표시
- 🎨 **반응형 디자인** PC/모바일 지원

## 🌐 라이브 데모

**배포된 사이트**: [https://your-project.vercel.app](https://your-project.vercel.app)

## 🛠️ 기술 스택

- **Backend**: Python Flask
- **Frontend**: HTML5, CSS3, JavaScript
- **OCR**: NAVER CLOVA OCR API
- **QR Code**: qrcode 라이브러리
- **Deployment**: Vercel

## 📦 빠른 시작

### 1. 저장소 클론
```bash
git clone https://github.com/your-username/business-card-vercel.git
cd business-card-vercel
```

### 2. 환경 설정
```bash
# 가상환경 생성
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 의존성 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일에 실제 API 키 입력
```

### 3. 로컬 실행
```bash
python app.py
```

브라우저에서 `http://localhost:5000` 접속

## 🔧 배포 설정

### NAVER CLOVA OCR API 설정

1. **NAVER Cloud Platform 계정 생성**
   - [ncloud.com](https://www.ncloud.com) 가입
   - 본인 인증 완료

2. **CLOVA OCR 서비스 신청**
   - 콘솔 > AI·NAVER API > CLOVA OCR
   - Document OCR 또는 Business Card OCR 선택
   - 이용 신청

3. **API 키 발급**
   - 콘솔 > 마이페이지 > 인증키 관리
   - Secret Key 생성 및 복사
   - Invoke URL 확인

### Vercel 배포

1. **GitHub 연동**
   ```bash
   git remote add origin https://github.com/your-username/business-card-vercel.git
   git push -u origin main
   ```

2. **Vercel 프로젝트 생성**
   - [vercel.com](https://vercel.com) 로그인
   - "Import Project" > GitHub 저장소 선택
   - Framework: **Other** 선택

3. **환경 변수 설정**
   - Vercel Dashboard > Settings > Environment Variables
   ```
   NAVER_OCR_SECRET_KEY = your_secret_key
   NAVER_OCR_INVOKE_URL = your_invoke_url
   ```

4. **배포 완료**
   - 자동 배포 시작
   - 완료 후 도메인 확인

## 📁 프로젝트 구조

```
business-card-vercel/
├── app.py                 # Flask 메인 애플리케이션
├── requirements.txt       # Python 의존성
├── vercel.json           # Vercel 배포 설정
├── .env.example          # 환경 변수 템플릿
├── .gitignore            # Git 제외 파일
└── README.md             # 프로젝트 문서
```

## 🔗 API 엔드포인트

### `GET /`
메인 페이지 (웹 인터페이스)

### `POST /api/process-business-card`
명함 이미지 처리
- **Content-Type**: `multipart/form-data`
- **Body**: `image` (파일)
- **Response**: 추출된 연락처 정보

### `POST /api/generate-files`
VCF 파일 및 QR 코드 생성
- **Content-Type**: `application/json`
- **Body**: `contactData` (객체)
- **Response**: VCF 내용 및 QR 코드 (Base64)

### `GET /api/download-vcf`
VCF 파일 다운로드
- **Query**: `data` (JSON 문자열)
- **Response**: VCF 파일

### `GET /api/health`
서비스 상태 확인
- **Response**: 서버 상태 및 설정 정보

## 📱 사용 방법

1. **명함 업로드**
   - 메인 페이지에서 명함 이미지 업로드
   - 지원 형식: JPG, PNG (최대 16MB)

2. **자동 처리**
   - NAVER CLOVA OCR이 텍스트 추출
   - AI가 연락처 정보 구조화

3. **정보 확인 및 수정**
   - 좌측 패널에서 추출된 정보 확인
   - 우측 패널에서 실시간 미리보기
   - 필요시 정보 수정

4. **파일 생성**
   - VCF 파일 자동 생성
   - QR 코드 표시
   - 다운로드 링크 제공

## 🔍 지원되는 정보

- ✅ **이름** (한글/영문)
- ✅ **직책** (팀장, CEO, Manager 등)
- ✅ **회사명** (주식회사, Inc, Corp 등)
- ✅ **전화번호** (010-1234-5678 형식)
- ✅ **이메일** (example@company.com)
- ✅ **주소** (도로명, 지번 주소)

## 🌏 다국어 지원

- **한국어**: 완전 지원
- **영어**: 기본 지원
- **일본어**: 부분 지원 (OCR 설정 변경 필요)

## 📊 성능 지표

- **OCR 처리 시간**: 평균 3-5초
- **파일 생성**: 1초 이내
- **지원 이미지 크기**: 최대 16MB
- **동시 사용자**: Vercel Hobby 플랜 기준 제한 없음

## 🔒 보안 및 개인정보

- **데이터 저장**: 서버에 개인정보 저장하지 않음
- **이미지 처리**: 임시 메모리에서만 처리
- **통신 보안**: HTTPS 암호화 통신
- **API 키**: 환경 변수로 안전 관리

## 💰 비용 정보

### Vercel 호스팅
- **Hobby 플랜**: 무료
  - 월 100GB-시간 함수 실행
  - 월 100GB 대역폭
  - 개인/소규모 프로젝트 적합

### NAVER CLOVA OCR
- **무료 크레딧**: 신규 가입시 100,000원
- **Document OCR**: 건당 10원
- **Business Card OCR**: 건당 30원
- **월 예상 비용**: 1,000건 처리시 약 10,000-30,000원

## 🐛 문제 해결

### 일반적인 문제

**1. OCR 인식률이 낮음**
- 해결방법: 명함을 밝은 곳에서 정면으로 촬영
- 권장: 300DPI 이상, 단색 배경

**2. API 오류 (401/403)**
- 해결방법: NAVER OCR API 키 확인
- 확인사항: 환경 변수 설정, 서비스 활성화

**3. 파일 업로드 실패**
- 해결방법: 파일 크기 및 형식 확인
- 제한사항: 16MB 이하, JPG/PNG만 지원

**4. 배포 오류**
- 해결방법: Vercel 로그 확인
- 확인사항: requirements.txt, 환경 변수

### 로그 확인 방법

```bash
# Vercel CLI로 로그 확인
vercel logs

# 실시간 로그 모니터링
vercel logs --follow
```

## 📈 업데이트 계획

- [ ] **다국어 인터페이스** (영어, 일본어)
- [ ] **이미지 전처리** 자동 향상
- [ ] **배치 처리** 여러 명함 동시 처리
- [ ] **API 통계** 사용량 대시보드
- [ ] **커스텀 도메인** 연결 가이드

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📞 지원 및 문의

- **GitHub Issues**: 버그 리포트 및 기능 요청
- **이메일**: your-email@example.com
- **공식 문서**: [NAVER CLOVA OCR API](https://www.ncloud.com/product/aiService/ocr)

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

## 🙏 감사의 말

- **NAVER Cloud Platform**: OCR API 제공
- **Vercel**: 무료 호스팅 플랫폼 제공
- **Flask**: 간단하고 강력한 웹 프레임워크
- **오픈소스 커뮤니티**: 다양한 라이브러리 제공

---

⭐ 이 프로젝트가 도움이 되셨다면 Star를 눌러주세요!

**Live Demo**: [https://your-project.vercel.app](https://your-project.vercel.app)