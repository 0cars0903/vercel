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

# pipeline_card.py의 핵심 로직 통합
import ollama
import dotenv
dotenv.load_dotenv()

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024  # 32MB max file size

# 환경 변수
NAVER_OCR_SECRET_KEY = os.environ.get('NAVER_OCR_SECRET_KEY')
NAVER_OCR_INVOKE_URL = os.environ.get('NAVER_OCR_INVOKE_URL')

# HTML 템플릿 (수정된 버전)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Business Card Processor v2.2</title>
    <style>
        :root {
            --primary-color: #1877f2;
            --primary-hover: #166fe5;
            --secondary-bg: #e4e6eb;
            --secondary-hover: #d8dbdf;
            --background-color: #f0f2f5;
            --panel-bg: #ffffff;
            --text-primary: #1c1e21;
            --text-secondary: #666;
            --border-color: #ccd0d5;
            --border-radius: 12px;
            --shadow: 0 4px 12px rgba(0,0,0,0.1);
        }
        *, *::before, *::after { box-sizing: border-box; }
        body, h1, h2, p, ul, li { margin: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: var(--background-color);
            color: var(--text-primary);
            line-height: 1.5;
            min-height: 100vh;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 2rem; }
        header { text-align: center; margin-bottom: 2rem; }
        .main-layout { 
            display: grid; 
            grid-template-columns: 1fr 1.2fr 1fr; 
            gap: 2rem; 
            align-items: stretch; /* This makes all panels equal height */
        }
        .panel { 
            background: var(--panel-bg); 
            border-radius: var(--border-radius); 
            box-shadow: var(--shadow); 
            padding: 2rem;
            display: flex;
            flex-direction: column;
        }
        .panel h2 { color: #333; margin-bottom: 1.5rem; border-bottom: 1px solid var(--secondary-bg); padding-bottom: 1rem; }
        .mode-selection { display: flex; gap: 1rem; margin-bottom: 2rem; }
        .btn {
            display: inline-block; padding: 0.75rem 1.5rem; border: none; border-radius: 8px;
            font-size: 1rem; font-weight: 600; cursor: pointer; transition: all 0.2s ease;
            text-decoration: none; text-align: center;
        }
        .btn-primary { background-color: var(--primary-color); color: var(--panel-bg); }
        .btn-primary:hover { background-color: var(--primary-hover); transform: translateY(-2px); }
        .btn-secondary { background-color: var(--secondary-bg); color: var(--text-primary); }
        .btn-secondary:hover { background-color: var(--secondary-hover); }
        .upload-area {
            border: 2px dashed var(--border-color); border-radius: 8px; padding: 2rem; text-align: center;
            background-color: #f7f8fa; cursor: pointer; transition: background-color 0.2s;
            min-height: 120px; display: flex; align-items: center; justify-content: center; flex-direction: column;
        }
        .upload-area:hover, .upload-area.dragover { background-color: var(--secondary-bg); }
        .upload-area p { margin: 0; font-size: 1rem; color: var(--text-secondary); }
        .hidden { display: none !important; }
        .input-group { margin-bottom: 1rem; }
        .input-group label { display: block; font-weight: 600; margin-bottom: 0.5rem; }
        .input-group input {
            width: 100%; padding: 0.75rem; border: 1px solid var(--border-color);
            border-radius: 6px; font-size: 1rem;
        }
        .result-list { list-style: none; padding: 0; max-height: 65vh; overflow-y: auto; }
        .result-item {
            display: flex; align-items: center; padding: 1rem; border-radius: 8px;
            margin-bottom: 0.5rem; cursor: pointer; transition: background-color 0.2s;
        }
        .result-item.active, .result-item:hover { background-color: #e7f3ff; }
        .result-item img { width: 80px; height: 50px; object-fit: cover; border-radius: 4px; margin-right: 1rem; }
        .result-item-info { flex-grow: 1; }
        .result-item-info p { margin: 0; }
        .qr-code img { max-width: 150px; margin: 1rem auto; display: block; }
        
        /* Panel Content Growth */
        #editor-panel > div, #results-panel > div {
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }
        #editor-empty-state, #results-empty-state {
            flex-grow: 1;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Dynamic Loader Styles */
        .loader {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(255,255,255,0.9); backdrop-filter: blur(5px);
            display: flex; align-items: center; justify-content: center; z-index: 999;
        }
        .loader-content {
            background: white; padding: 2rem 3rem; border-radius: 12px;
            box-shadow: var(--shadow); text-align: center;
        }
        .loader-steps { list-style: none; padding: 0; margin: 1.5rem 0; text-align: left; }
        .loader-steps li { display: flex; align-items: center; margin-bottom: 1rem; opacity: 0.5; transition: opacity 0.3s ease; font-size: 1.1rem; }
        .loader-steps li.in-progress, .loader-steps li.completed { opacity: 1; }
        .status-icon {
            width: 24px; height: 24px; border-radius: 50%; border: 2px solid var(--border-color);
            margin-right: 1rem; position: relative; transition: all 0.3s ease;
        }
        .in-progress .status-icon {
            border-color: transparent; border-top-color: var(--primary-color);
            animation: spin 1s linear infinite;
        }
        .completed .status-icon { background-color: var(--primary-color); border-color: var(--primary-color); }
        .completed .status-icon::after {
            content: ''; position: absolute; left: 8px; top: 4px; width: 5px; height: 10px;
            border: solid white; border-width: 0 3px 3px 0; transform: rotate(45deg);
        }
        @keyframes spin { 100% { transform: rotate(360deg); } }
        
        .action-buttons { margin-top: 1.5rem; display: flex; gap: 0.5rem; justify-content: center; }
        @media (max-width: 1200px) { .main-layout { grid-template-columns: 1fr 1fr; } #editor-panel { grid-column: span 2; } }
        @media (max-width: 768px) { .main-layout { grid-template-columns: 1fr; } }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>AI 명함 처리 시스템 v2.2</h1>
            <p>동적 로딩 UI 및 레이아웃이 개선되었습니다.</p>
        </header>

        <div class="main-layout">
            <!-- Left Panel: Upload -->
            <div class="panel" id="upload-panel">
                <h2>1. 명함 업로드</h2>
                <div class="mode-selection">
                    <button class="btn btn-primary" id="batch-mode-btn" onclick="switchMode('batch')">다중 처리</button>
                    <button class="btn btn-secondary" id="two-sided-mode-btn" onclick="switchMode('two-sided')">양면 처리</button>
                </div>
                
                <div id="batch-mode-ui">
                    <div class="upload-area" id="batch-upload-area"><p>파일을 드래그하거나 클릭</p></div>
                    <input type="file" id="batch-file-input" multiple accept="image/*" class="hidden">
                    <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" onclick="processBatchFiles()">일괄 처리 시작</button>
                </div>

                <div id="two-sided-mode-ui" class="hidden">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                        <div class="upload-area" id="front-upload-area"><p>앞면 (한글)</p></div>
                        <div class="upload-area" id="back-upload-area"><p>뒷면 (영문)</p></div>
                    </div>
                    <input type="file" id="front-file-input" accept="image/*" class="hidden">
                    <input type="file" id="back-file-input" accept="image/*" class="hidden">
                    <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" onclick="processTwoSidedFiles()">양면 처리 시작</button>
                </div>
            </div>

            <!-- Center Panel: Edit -->
            <div class="panel" id="editor-panel">
                <h2>2. 정보 수정</h2>
                <div id="editor-ui" class="hidden">
                    <div id="editor-form" style="max-height: 60vh; overflow-y: auto; padding-right: 1rem;"></div>
                    <button class="btn btn-primary" style="width: 100%; margin-top: 1rem;" onclick="updateItemData()">수정 내용 저장</button>
                </div>
                <div id="editor-empty-state">
                    <p>좌측에서 명함을 처리하거나<br>우측 목록에서 항목을 선택하면<br>여기에 수정 폼이 표시됩니다.</p>
                </div>
            </div>

            <!-- Right Panel: Results -->
            <div class="panel" id="results-panel">
                <h2>3. 결과 확인</h2>
                <!-- Batch Results -->
                <div id="batch-results-ui" class="hidden">
                    <input type="text" class="input-group" id="filter-input" placeholder="이름, 회사 등으로 필터링..." onkeyup="filterResults()">
                    <ul class="result-list" id="result-list"></ul>
                    <hr style="margin: 1rem 0;">
                    <div id="batch-item-details" class="hidden">
                         <div class="qr-code" id="batch-qr-code"></div>
                         <div class="action-buttons">
                            <a href="#" id="batch-vcf-download" class="btn btn-primary">VCF 다운로드</a>
                            <a href="#" id="batch-qr-download" class="btn btn-secondary">QR 코드 저장</a>
                        </div>
                    </div>
                    <div id="download-section" style="margin-top: 1.5rem;">
                         <button class="btn btn-primary" style="width: 100%;" onclick="downloadBatch()">전체 VCF 다운로드</button>
                         <p id="download-notice" style="font-size: 0.9rem; color: var(--text-secondary); margin-top: 0.5rem; text-align:center;"></p>
                    </div>
                </div>
                <!-- Single (Two-sided) Results -->
                <div id="single-result-ui" class="hidden">
                    <div class="qr-code" id="qr-code-display"></div>
                    <div class="action-buttons">
                        <a href="#" id="vcf-download-link" class="btn btn-primary">VCF 다운로드</a>
                        <a href="#" id="qr-download-link" class="btn btn-secondary">QR 코드 저장</a>
                    </div>
                </div>
                <!-- Empty State -->
                <div id="results-empty-state">
                    <p>좌측에서 명함을 업로드하면<br>여기에 결과가 표시됩니다.</p>
                </div>
            </div>
        </div>
    </div>

    <div class="loader hidden" id="loader">
        <div class="loader-content">
            <h3>처리 중입니다...</h3>
            <ul class="loader-steps">
                <li id="step-1"><div class="status-icon"></div><span>OCR 처리</span></li>
                <li id="step-2"><div class="status-icon"></div><span>정보 추출</span></li>
                <li id="step-3"><div class="status-icon"></div><span>VCF/QR 생성</span></li>
            </ul>
            <p id="loader-message">잠시만 기다려주세요.</p>
        </div>
    </div>
    
    <script>
    // --- State Management ---
    let currentMode = 'batch';
    let batchData = [];
    let activeItemId = null;
    let singleResultData = null;

    document.addEventListener('DOMContentLoaded', () => {
        initializeEventListeners();
        switchMode('batch');
    });

    function switchMode(mode) {
        currentMode = mode;
        document.getElementById('batch-mode-btn').className = mode === 'batch' ? 'btn btn-primary' : 'btn btn-secondary';
        document.getElementById('two-sided-mode-btn').className = mode === 'two-sided' ? 'btn btn-primary' : 'btn btn-secondary';
        document.getElementById('batch-mode-ui').classList.toggle('hidden', mode !== 'batch');
        document.getElementById('two-sided-mode-ui').classList.toggle('hidden', mode !== 'two-sided');
        updatePanelsVisibility();
    }

    function updatePanelsVisibility() {
        const hasBatchData = batchData.length > 0;
        const hasSingleData = singleResultData !== null;
        const isItemSelected = activeItemId !== null;

        document.getElementById('batch-results-ui').classList.toggle('hidden', currentMode !== 'batch' || !hasBatchData);
        document.getElementById('single-result-ui').classList.toggle('hidden', currentMode !== 'two-sided' || !hasSingleData);
        document.getElementById('results-empty-state').classList.toggle('hidden', (currentMode === 'batch' && hasBatchData) || (currentMode === 'two-sided' && hasSingleData));
        
        const showEditor = (currentMode === 'batch' && isItemSelected) || (currentMode === 'two-sided' && hasSingleData);
        document.getElementById('editor-ui').classList.toggle('hidden', !showEditor);
        document.getElementById('editor-empty-state').classList.toggle('hidden', showEditor);
    }
    
    // --- Reset Functions ---
    function resetBatchState() {
        batchData = []; activeItemId = null;
        document.getElementById('result-list').innerHTML = '';
        document.getElementById('filter-input').value = '';
        document.getElementById('batch-item-details').classList.add('hidden');
        updatePanelsVisibility();
    }
    function resetSingleState() { singleResultData = null; updatePanelsVisibility(); }

    // --- Event Listeners ---
    function initializeEventListeners() {
        const uploadConfigs = [
            { areaId: 'batch-upload-area', inputId: 'batch-file-input' },
            { areaId: 'front-upload-area', inputId: 'front-file-input' },
            { areaId: 'back-upload-area', inputId: 'back-file-input' }
        ];
        uploadConfigs.forEach(({ areaId, inputId }) => {
            const area = document.getElementById(areaId), input = document.getElementById(inputId);
            if (!area || !input) return;
            area.addEventListener('click', () => input.click());
            area.addEventListener('dragover', e => { e.preventDefault(); area.classList.add('dragover'); });
            area.addEventListener('dragleave', () => area.classList.remove('dragover'));
            area.addEventListener('drop', e => {
                e.preventDefault(); area.classList.remove('dragover');
                if (e.dataTransfer.files.length > 0) {
                    input.files = e.dataTransfer.files;
                    updateUploadAreaText(area, input.files);
                }
            });
            input.addEventListener('change', e => updateUploadAreaText(area, e.target.files));
        });
    }

    function updateUploadAreaText(area, files) {
        const p = area.querySelector('p');
        p.textContent = files.length > 0 ? `${files.length}개 파일 선택됨` : area.id.includes('batch') ? '파일을 드래그하거나 클릭' : area.id.includes('front') ? '앞면 (한글)' : '뒷면 (영문)';
        area.style.backgroundColor = files.length > 0 ? '#e7f3ff' : '#f7f8fa';
    }

    // --- Dynamic Loader ---
    function updateLoaderStep(stepIndex, status) {
        const steps = document.querySelectorAll('.loader-steps li');
        if (steps[stepIndex]) {
            steps[stepIndex].className = status || '';
        }
    }

    function showLoader(isProcessing = true) {
        document.getElementById('loader').classList.remove('hidden');
        document.querySelector('.loader-steps').style.display = isProcessing ? 'block' : 'none';
        document.querySelector('.loader-content h3').textContent = isProcessing ? '처리 중입니다...' : '생성 중입니다...';
        for (let i = 0; i < 3; i++) updateLoaderStep(i, null);
    }
    const hideLoader = () => document.getElementById('loader').classList.add('hidden');

    // --- UI Rendering ---
    function renderBatchResults() {
        const listEl = document.getElementById('result-list');
        listEl.innerHTML = '';
        const keyword = document.getElementById('filter-input').value.toLowerCase();
        
        batchData.filter(item => JSON.stringify(item.data).toLowerCase().includes(keyword))
            .forEach(item => {
                const li = document.createElement('li');
                li.className = `result-item ${item.id === activeItemId ? 'active' : ''}`;
                li.id = `item-${item.id}`;
                li.onclick = () => selectItem(item.id);
                li.innerHTML = `<img src="data:image/jpeg;base64,${item.thumbnail}" alt="thumbnail"><div class="result-item-info"><p style="font-weight: 600;">${item.data.name||'이름 없음'}</p><p style="font-size: 0.9rem; color: var(--text-secondary);">${item.data.company||'회사 정보 없음'}</p></div>`;
                listEl.appendChild(li);
            });
        
        document.getElementById('download-notice').textContent = batchData.length >= 2 ? `총 ${batchData.length}개의 VCF가 zip 파일로 다운로드됩니다.` : 'VCF 파일이 다운로드됩니다.';
        updatePanelsVisibility();
    }
    
    function filterResults() { renderBatchResults(); }

    async function selectItem(itemId) {
        activeItemId = itemId;
        const item = batchData.find(d => d.id === itemId);
        if (!item) return;

        renderBatchResults();
        renderEditor(item.data, false);
        
        // 사용자의 요청에 따라, 항목 선택 시 로더가 표시되지 않도록 수정했습니다.
        generateQrAndVcf(item.data, 'batch', false);
        
        document.getElementById('batch-item-details').classList.remove('hidden');
        updatePanelsVisibility();
    }
    
    function renderEditor(data, isTwoSided) {
        const formEl = document.getElementById('editor-form');
        formEl.innerHTML = '';
        const fields = isTwoSided
            ? { name_ko: '이름(한글)', name_en: '이름(영문)', title_ko: '직책(한글)', title_en: '직책(영문)', company_ko: '회사(한글)', company_en: '회사(영문)', phone: '전화번호', email: '이메일', address_ko: '주소(한글)', address_en: '주소(영문)' }
            : { name: '이름', title: '직책', company: '회사', phone: '전화번호', email: '이메일', address: '주소' };

        for (const [key, label] of Object.entries(fields)) {
            formEl.innerHTML += `<div class="input-group"><label for="edit-${key}">${label}</label><input type="text" id="edit-${key}" value="${data[key] || ''}"></div>`;
        }
    }
    
    // --- API Calls ---
    async function processFiles(apiEndpoint, formData) {
        showLoader(true);
        try {
            updateLoaderStep(0, 'in-progress'); // Step 1: OCR
            await new Promise(r => setTimeout(r, 500)); // Simulate work
            
            updateLoaderStep(0, 'completed');
            updateLoaderStep(1, 'in-progress'); // Step 2: Extract
            
            const response = await fetch(apiEndpoint, { method: 'POST', body: formData });
            const result = await response.json();

            if (!result.success) throw new Error(result.error);
            
            updateLoaderStep(1, 'completed');
            updateLoaderStep(2, 'in-progress'); // Step 3: VCF/QR
            
            const contactInfo = result.contactInfo || (result.results ? result.results : null);
            if (!contactInfo) throw new Error('No contact info processed.');
            
            return result;
        } finally {
            // Loader will be hidden by the calling function after VCF generation
        }
    }

    async function processBatchFiles() {
        const { files } = document.getElementById('batch-file-input');
        if (files.length === 0) return alert('파일을 선택해주세요.');
        
        resetBatchState();
        const formData = new FormData();
        for(const file of files) formData.append('images', file);
        
        try {
            const result = await processFiles('/api/process-batch', formData);
            batchData = result.results;
            updateLoaderStep(2, 'completed'); // Mark final step as complete for batch
            renderBatchResults();
        } catch (error) {
            alert('오류: ' + error.message);
        } finally {
            await new Promise(r => setTimeout(r, 500));
            hideLoader();
        }
    }

    async function processTwoSidedFiles() {
        const frontFile = document.getElementById('front-file-input').files[0];
        const backFile = document.getElementById('back-file-input').files[0];
        if (!frontFile || !backFile) return alert('앞면과 뒷면 파일을 모두 선택해주세요.');
        
        resetSingleState();
        const formData = new FormData();
        formData.append('frontImage', frontFile);
        formData.append('backImage', backFile);
        
        try {
            const result = await processFiles('/api/process-two-sided', formData);
            await generateQrAndVcf(result.contactInfo, 'single', false);
            
            updateLoaderStep(2, 'completed');
            
            singleResultData = result.contactInfo;
            renderEditor(singleResultData, true);
            updatePanelsVisibility();
        } catch (error) {
            alert('처리 중 오류가 발생했습니다: ' + error.message);
        } finally {
            await new Promise(r => setTimeout(r, 500));
            hideLoader();
        }
    }
    
    async function downloadBatch() {
        if (batchData.length === 0) return alert('다운로드할 데이터가 없습니다.');
        showLoader(false);
        try {
            const response = await fetch('/api/download-batch', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ items: batchData })
            });
            if (response.ok) {
                const blob = await response.blob(), url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const disposition = response.headers.get('Content-Disposition');
                let filename = 'contacts.zip';
                if (disposition) {
                    const match = disposition.match(/filename="(.+)"/);
                    if (match) filename = match[1];
                }
                a.download = filename; a.click(); window.URL.revokeObjectURL(url);
            } else alert('다운로드 실패');
        } catch (error) { alert('다운로드 중 오류가 발생했습니다: ' + error.message); } 
        finally { hideLoader(); }
    }

    function updateItemData() {
        let dataObject;
        if (currentMode === 'batch') {
            if (!activeItemId) return alert('수정할 항목을 선택해주세요.');
            const item = batchData.find(d => d.id === activeItemId);
            if (!item) return; dataObject = item.data;
        } else {
            if (!singleResultData) return alert('수정할 데이터가 없습니다.');
            dataObject = singleResultData;
        }
        const form = document.getElementById('editor-form');
        form.querySelectorAll('input').forEach(input => {
            const key = input.id.replace('edit-', '');
            if (key in dataObject) dataObject[key] = input.value;
        });
        alert('저장되었습니다.');
        if (currentMode === 'batch') {
            renderBatchResults(); selectItem(activeItemId);
        } else {
            renderEditor(dataObject, true); generateQrAndVcf(dataObject, 'single');
        }
    }

    async function generateQrAndVcf(data, type, showOwnLoader = true) {
        if (showOwnLoader) showLoader(false);
        try {
            const response = await fetch('/api/generate-vcf-qr', {
                method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ contactData: data })
            });
            const result = await response.json();
            if (!result.success) throw new Error(result.error);

            const name = data.name_en || data.name_ko || data.name || 'contact';
            const qrImgSrc = `data:image/png;base64,${result.qrCode}`;
            
            const ids = type === 'batch' 
                ? { qr: 'batch-qr-code', vcf: 'batch-vcf-download', qrLink: 'batch-qr-download' }
                : { qr: 'qr-code-display', vcf: 'vcf-download-link', qrLink: 'qr-download-link' };

            document.getElementById(ids.qr).innerHTML = `<img src="${qrImgSrc}" alt="QR Code">`;
            const vcfLink = document.getElementById(ids.vcf);
            vcfLink.href = URL.createObjectURL(new Blob([result.vcfContent], { type: 'text/vcard' }));
            vcfLink.download = `${name}.vcf`;
            
            const qrLink = document.getElementById(ids.qrLink);
            qrLink.href = qrImgSrc;
            qrLink.download = `${name}_qrcode.png`;
        } finally {
            if (showOwnLoader) hideLoader();
        }
    }
    </script>
</body>
</html>
"""

# ==========================================================================
# 명함 처리 에이전트 및 헬퍼 함수
# ==========================================================================

def ocr_agent(image_path: str) -> list[dict]:
    """NAVER CLOVA OCR API를 사용하여 이미지에서 텍스트 추출"""
    print(f"\n[ OCR Agent ] Processing '{os.path.basename(image_path)}'...")
    
    if not NAVER_OCR_SECRET_KEY or not NAVER_OCR_INVOKE_URL:
        print("[Error] NAVER CLOVA OCR 환경 변수가 설정되지 않았습니다.")
        return []
    
    request_body = {
        'version': 'V2',
        'requestId': 'NCP-OCR-ID-' + str(int(time.time() * 1000)),
        'timestamp': int(time.time() * 1000),
        'lang': 'ko',
        'images': [{
            'format': os.path.splitext(image_path)[1][1:].upper(),
            'name': os.path.basename(image_path)
        }]
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
        
        result_json = response.json()
        full_text = ""
        
        for image_result in result_json.get('images', []):
            for field in image_result.get('fields', []):
                full_text += field.get('inferText', '') + " "
        
        # 간단한 문장 분리
        sentences = [s.strip() for s in full_text.strip().replace('\n', ' ').split('.') if s.strip()]
        return [{'id': idx + 1, 'text': sentence} for idx, sentence in enumerate(sentences)]
        
    except Exception as e:
        print(f"[OCR Error] {e}")
        return []

def extract_structured_info_with_retry(raw_text: str, model_name: str = 'mistral:latest') -> dict:
    """Ollama를 사용하여 텍스트에서 구조화된 정보 추출"""
    prompt = f"""You are an expert business card information extractor. From the provided text, extract the required information into a valid JSON format. For missing information, use an empty string "". Return ONLY valid JSON.

    Required JSON structure: {{"name": "", "title": "", "company": "", "phone": "", "email": "", "address": ""}}
    
    --- Text to Analyze ---
    {raw_text}"""
    
    try:
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            format='json',
            options={'temperature': 0.1}
        )
        
        content = response['message']['content']
        if isinstance(content, str):
            return json.loads(content)
        return content
        
    except Exception as e:
        print(f"[LLM Error] {e}")
        return {"name": "", "title": "", "company": "", "phone": "", "email": "", "address": ""}

def two_sided_extract_agent(front_text: str, back_text: str, model_name: str = 'mistral:latest') -> dict:
    """양면 명함 분석을 위한 Ollama 에이전트"""
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
        response = ollama.chat(
            model=model_name,
            messages=[{'role': 'user', 'content': prompt}],
            format='json',
            options={'temperature': 0.1}
        )
        
        content = response['message']['content']
        if isinstance(content, str):
            return json.loads(content)
        return content

    except Exception as e:
        print(f"[Two-sided LLM Error] {e}")
        return {"name_ko": "", "name_en": "", "title_ko": "", "title_en": "", "company_ko": "", "company_en": "", "phone": "", "email": "", "address_ko": "", "address_en": ""}


def generate_vcf_content(data: dict) -> str:
    """양면 지원 VCF 생성 함수"""
    vcf_lines = ["BEGIN:VCARD", "VERSION:3.0"]
    
    name_ko = data.get('name_ko') or data.get('name', '')
    name_en = data.get('name_en', '')
    
    # FN과 N 필드 설정
    if name_ko and name_en:
        vcf_lines.append(f"FN;CHARSET=UTF-8:{name_ko} {name_en}")
        vcf_lines.append(f"N;CHARSET=UTF-8:{name_ko};{name_en};;;")
    elif name_ko:
        vcf_lines.append(f"FN;CHARSET=UTF-8:{name_ko}")
        vcf_lines.append(f"N;CHARSET=UTF-8:{name_ko};;;;")
    elif name_en:
        vcf_lines.append(f"FN;CHARSET=UTF-8:{name_en}")
        vcf_lines.append(f"N;CHARSET=UTF-8:{name_en};;;;")

    title_ko = data.get('title_ko') or data.get('title', '')
    title_en = data.get('title_en', '')
    if title_ko or title_en:
        full_title = f"{title_ko}{' / ' if title_ko and title_en else ''}{title_en}"
        vcf_lines.append(f"TITLE;CHARSET=UTF-8:{full_title}")
    
    company_ko = data.get('company_ko') or data.get('company', '')
    company_en = data.get('company_en', '')
    if company_ko or company_en:
        full_company = f"{company_ko}{' / ' if company_ko and company_en else ''}{company_en}"
        vcf_lines.append(f"ORG;CHARSET=UTF-8:{full_company}")
    
    # 공통 필드
    if data.get('phone'):
        vcf_lines.append(f"TEL;TYPE=WORK,VOICE:{data['phone']}")
    if data.get('email'):
        vcf_lines.append(f"EMAIL;TYPE=WORK:{data['email']}")
    
    address = data.get('address_ko', '') or data.get('address', '')
    if address:
        vcf_lines.append(f"ADR;TYPE=WORK;CHARSET=UTF-8:;;{address};;;;")
    
    vcf_lines.append(f"REV:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}")
    vcf_lines.append("END:VCARD")
    
    return '\n'.join(vcf_lines)

def generate_qr_code(vcf_content):
    """QR 코드 생성 함수"""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4
    )
    qr.add_data(vcf_content)
    qr.make(fit=True)
    
    qr_image = qr.make_image(fill_color="black", back_color="white")
    img_buffer = io.BytesIO()
    qr_image.save(img_buffer, format='PNG')
    return base64.b64encode(img_buffer.getvalue()).decode()

# ==========================================================================
# Flask API Endpoints
# ==========================================================================

@app.route('/')
def index():
    """메인 페이지"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/process-batch', methods=['POST'])
def process_batch():
    """다중 명함 일괄 처리 API"""
    try:
        files = request.files.getlist('images')
        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': '이미지 파일이 필요합니다.'})

        results = []
        with tempfile.TemporaryDirectory() as temp_dir:
            for idx, file in enumerate(files):
                filename = secure_filename(file.filename)
                temp_path = os.path.join(temp_dir, filename)
                file.save(temp_path)
                
                ocr_list = ocr_agent(temp_path)
                if not ocr_list:
                    continue
                
                full_text = ' '.join([item['text'] for item in ocr_list])
                contact_info = extract_structured_info_with_retry(full_text)
                
                file.seek(0)
                thumbnail = base64.b64encode(file.read()).decode('utf-8')

                results.append({
                    'id': f"card-{int(time.time() * 1000)}-{idx}",
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

        if len(items_to_download) == 1:
            item = items_to_download[0]
            vcf_content = generate_vcf_content(item['data'])
            name = item['data'].get('name_ko') or item['data'].get('name', 'contact')
            safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
            
            buffer = io.BytesIO(vcf_content.encode('utf-8'))
            buffer.seek(0)
            
            return send_file(buffer, as_attachment=True, download_name=f"{safe_name}.vcf", mimetype='text/vcard')

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for item in items_to_download:
                vcf_content = generate_vcf_content(item['data'])
                name = item['data'].get('name_ko') or item['data'].get('name', 'contact')
                safe_name = re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')
                zf.writestr(f"{safe_name}.vcf", vcf_content)
        
        memory_file.seek(0)
        zip_filename = f"contacts_{datetime.now().strftime('%Y%m%d')}.zip"
        return send_file(memory_file, as_attachment=True, download_name=zip_filename, mimetype='application/zip')
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/health')
def health_check():
    """헬스 체크"""
    return jsonify({
        'status': 'healthy',
        'version': '2.2',
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🚀 AI 명함 처리 시스템 v2.2 시작!")
    print("================================")
    
    if not NAVER_OCR_SECRET_KEY or not NAVER_OCR_INVOKE_URL:
        print("⚠️ NAVER CLOVA OCR 환경 변수가 설정되지 않았습니다!")
    
    try:
        models = ollama.list()
        print(f"✅ Ollama 연결 성공! 사용 가능한 모델: {[m['name'] for m in models.get('models', [])]}")
    except Exception as e:
        print(f"❌ Ollama 연결 실패: {e}. 'ollama serve'를 실행하세요.")
    
    print("\n📱 http://localhost:5001 에서 접속 가능합니다.")
    app.run(debug=True, host='0.0.0.0', port=5001)


