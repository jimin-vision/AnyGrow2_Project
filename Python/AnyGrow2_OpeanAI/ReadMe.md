

# AnyGrow2 – Smart Farm Voice Assistant 🌱

센서 기반 스마트팜 상태를 **음성(STT)** 으로 입력받고,  
AI가 **식물(예: 상추) 캐릭터처럼 1인칭으로 대답**하며,  
필요 시 **스피커(TTS)** 로 음성 출력까지 수행하는 프로젝트입니다.

---

## 1. 개발 환경
- Python 3.11 이상
- macOS / Windows 지원
- 마이크(STT), 스피커(TTS)

---

## 2. 가상환경(venv) 생성 및 활성화

### macOS / Linux
```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows (PowerShell)
```powershell
python -m venv venv
venv\Scripts\activate
```

터미널 앞에 `(venv)` 표시가 나오면 정상입니다.

---

## 3. 필수 패키지 설치

```bash
pip install -r requirements.txt
```

> ⚠️ 최초 실행 시 Whisper STT 모델을 다운로드하므로 인터넷 연결이 필요합니다.

---

## 4. 환경 변수 설정 (.env)

프로젝트 루트에 `.env` 파일을 생성하고 아래 내용을 작성합니다.

```env
OPENAI_API_KEY=본인_API_KEY

PLANT_NAME=상추
OPENAI_MODEL=gpt-4o-mini

# TTS 설정
TTS_ENABLED=1
TTS_RATE=175
TTS_VOLUME=1.0

# Whisper STT (정확도 우선 프리셋)
WHISPER_MODEL=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE=int8
WHISPER_BEAM=5
WHISPER_BEST_OF=5
VAD_MIN_SILENCE_MS=500
CONDITION_ON_PREV=1

# 실행 모드
USE_STT=1
USE_STT_GUI=0
```

> `.env` 파일은 **Git에 커밋하지 않습니다** (`.gitignore` 처리 필수).

---

## 5. 실행 방법

```bash
python main.py
```

---

## 6. STT (음성 입력) 사용 방법

### CLI 방식 (Tkinter 없는 환경 / macOS pyenv 권장)

- **Enter** → 녹음 시작  
- **다시 Enter** → 녹음 종료 및 음성 인식  
- AI가 센서 상태를 반영해 답변 생성 + 음성 출력  
- `quit` 입력 시 종료

---

## 7. TTS (음성 출력)

- `pyttsx3` 기반
- mp3 파일 생성 없이 즉시 스피커 출력
- Windows / macOS 모두 지원

TTS 비활성화:
```env
TTS_ENABLED=0
```

---

## 8. Whisper 모델 파일 관리 (중요)

Whisper 모델은 실행 시 자동으로 로컬에 다운로드됩니다.

```text
.whisper_models/
```

❌ Git에 올리지 않습니다.

이미 추적 중이라면:
```bash
git rm -r --cached .whisper_models
git commit -m "chore: ignore whisper models"
```

---

## 9. 프로젝트 구조 예시

```text
AnyGrow2_Project/
├─ main.py
├─ example_STT.py
├─ requirements.txt
├─ ReadMe.md
├─ .gitignore
├─ .env            (gitignore)
├─ venv/           (gitignore)
└─ .whisper_models/ (gitignore)
```

---

## 10. 핵심 기능 요약
- 음성 입력(STT, Whisper)
- 센서 상태 기반 판단 로직
- 대화 맥락 유지
- 식물 캐릭터 1인칭 응답
- 음성 출력(TTS)
- GUI 없이도 완전 동작

---

## 11. 실행 문제 체크리스트
- 가상환경 활성화 여부
- `.env` 파일 존재 여부
- 마이크 권한 허용 여부
- Whisper 모델 다운로드 완료 여부

---

이 프로젝트는 **STT → AI 판단 → TTS** 파이프라인이 완성된 상태입니다.