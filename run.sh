#!/bin/bash

# AI 명함 처리 시스템 v2.0 실행 스크립트

echo "🚀 AI 명함 처리 시스템 v2.0 시작"
echo "=================================="

# 환경 확인
echo "📋 환경 확인 중..."

# Python 확인
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3이 설치되지 않았습니다."
    exit 1
fi

echo "✅ Python: $(python3 --version)"

# 가상환경 활성화
if [ -d "venv" ]; then
    echo "🔄 가상환경 활성화 중..."
    source venv/bin/activate
else
    echo "⚠️ 가상환경이 없습니다. 새로 생성합니다..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📦 의존성 설치 중..."
    pip install -r requirements.txt
fi

# .env 파일 확인
if [ ! -f ".env" ]; then
    echo "⚠️ .env 파일이 없습니다."
    echo "📝 .env 파일을 생성하세요:"
    echo "NAVER_OCR_SECRET_KEY=your_secret_key"
    echo "NAVER_OCR_INVOKE_URL=your_invoke_url"
    echo ""
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Ollama 확인
echo "🤖 Ollama 연결 확인 중..."
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama가 설치되지 않았습니다."
    echo "💡 https://ollama.ai 에서 설치하세요."
    exit 1
fi

# Ollama 서비스 확인
if ! pgrep -f "ollama serve" > /dev/null; then
    echo "🔄 Ollama 서비스 시작 중..."
    ollama serve &
    sleep 3
fi

# Mistral 모델 확인
if ! ollama list | grep -q "mistral"; then
    echo "📥 Mistral 모델 다운로드 중..."
    ollama pull mistral
fi

echo "✅ Ollama 준비 완료"

# Flask 애플리케이션 시작
echo ""
echo "🌐 웹 서버 시작 중..."
echo "📱 브라우저에서 http://localhost:5000 으로 접속하세요"
echo ""
echo "🛑 종료하려면 Ctrl+C를 누르세요"
echo ""

python app.py