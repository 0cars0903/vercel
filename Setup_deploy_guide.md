# AI 명함 처리 시스템 배포 가이드

이 문서는 Vercel에 프런트엔드를 배포하고, 로컬 환경에서 백엔드 API 서버를 실행하여 전체 시스템을 구동하는 방법을 안내합니다.

## 아키텍처 개요
> 프론트엔드 (Frontend): Frontend.html 파일.  

Vercel을 통해 정적 웹 페이지로 배포됩니다. 사용자의 모든 인터랙션은 이 페이지에서 이루어집니다.

> 백엔드 (Backend): FastAPI_backend.py 파일. 

로컬 컴퓨터에서 실행되는 FastAPI 기반의 API 서버입니다. OCR, Ollama LLM을 이용한 정보 추출, VCF/QR 코드 생성 등 모든 핵심 로직을 처리합니다.

> 두 시스템은 HTTP API 통신을 통해 데이터를 주고받습니다.

---

### 1단계: 로컬 백엔드 서버 설정 및 실행
로컬 컴퓨터에서 AI 및 데이터 처리 기능을 담당할 API 서버를 설정합니다.

> 사전 준비 : Python 3.8 이상 설치

  - ollama 설치 및 실행 (ollama serve 명령어로 실행)

 - 필요한 Ollama 모델 다운로드   

```
ollama pull mistral
```

> Python 라이브러리 설치:  

  - 터미널을 열고 아래 명령어를 실행
  -  FastAPI 서버 구동에 필요한 라이브러리들을 설치합니다.

```
pip install "fastapi[all]" uvicorn python-dotenv requests qrcode "Pillow" ollama
```

> .env 파일 생성:  

  - backend 파일과 동일한 위치에 .env 라는 이름의 파일을 생성
  - 그 안에 NAVER CLOVA OCR API 키 정보를 입력합니다.

```
NAVER_OCR_SECRET_KEY=여기에_시크릿_키를_입력하세요
NAVER_OCR_INVOKE_URL=여기에_Invoke_URL을_입력하세요
```

> Ollama 서버 실행:

  - 새로운 터미널 창을 열고 ollama serve 명령어를 실행하여 
  - Ollama 서버를 백그라운드에서 실행 상태로 둡니다.

> 백엔드 API 서버 실행:

  - 프로젝트 폴더로 이동한 후, 
  - 터미널에서 아래 명령어를 실행하여 백엔드 서버를 시작합니다.

```
uvicorn backend_main:app --host 0.0.0.0 --port 8000 --reload
```

서버가 정상적으로 실행되면 터미널에 Application startup complete. 메시지와 함께 http://localhost:8000 에서 실행 중이라는 안내가 나타납니다. 이 터미널 창은 Vercel 웹 페이지를 사용하는 동안 계속 실행 상태를 유지해야 합니다.

---

## 2단계: Vercel에 프런트엔드 배포

사용자가 접속할 웹 페이지를 Vercel에 배포합니다.

> 방법 1: 드래그 앤 드롭으로 배포 (가장 간단)
  - Vercel 대시보드에 로그인합니다.
  - Add New... -> Project를 선택합니다.
  - index.html 파일을 웹 브라우저의 Import Git Repository 섹션 아래에 있는 "Deploy a Project from your local directory" 영역으로 드래그 앤 드롭합니다.

  - 프로젝트 이름을 설정하고 Deploy 버튼을 클릭합니다.

  - 배포가 완료되면 제공되는 Vercel URL 로 접속하여 서비스를 사용할 수 있습니다.

> 방법 2: Git 연동으로 배포

  - index.html 파일을 GitHub, GitLab, 또는 Bitbucket 저장소에 푸시합니다.

 - Vercel 대시보드에서 Add New... -> Project를 선택합니다.

 - 해당 Git 저장소를 Import 합니다.

 - 프레임워크 프리셋(Framework Preset)을 Other로 두고 Deploy 버튼을 클릭합니다.

  - 배포가 완료되면 Vercel URL로 접속합니다.

---

### 3단계: 서비스 사용
로컬 백엔드 서버가 실행 중인지 확인합니다.

Vercel에 배포된 프런트엔드 URL로 접속합니다.

명함 이미지를 업로드하고 모든 기능이 정상적으로 동작하는지 테스트합니다.

중요: Vercel의 프런트엔드는 로컬의 백엔드 서버(http://localhost:8000)와 직접 통신합니다. 따라서 서비스를 사용하려면 반드시 로컬 컴퓨터에서 백엔드 서버가 실행되고 있어야 합니다.