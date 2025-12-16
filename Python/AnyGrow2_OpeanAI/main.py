import os
from dataclasses import dataclass, field
from collections import deque
import threading

from dotenv import load_dotenv
from openai import OpenAI

# =========================
# 환경 변수 로드 (.env)
# =========================
load_dotenv()

# =========================
# 캐릭터/설정
# =========================
PLANT_NAME = os.getenv("PLANT_NAME", "상추")
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# =========================
# STT (Push-to-talk) 연결
# =========================
USE_STT = os.getenv("USE_STT", "0") in {"1", "true", "True"}
USE_STT_GUI = os.getenv("USE_STT_GUI", "1") not in {"0", "false", "False"}

try:
    # example_STT.py에 있는 PushToTalkSTT 재사용
    from example_STT import PushToTalkSTT
except Exception:
    PushToTalkSTT = None  # type: ignore

try:
    import tkinter as tk
except Exception:
    tk = None

# =========================
# TTS (스피커 출력)
# - Windows: SAPI5 (pyttsx3)
# - macOS: NSSpeech (pyttsx3)
# =========================
TTS_ENABLED = os.getenv("TTS_ENABLED", "1") not in {"0", "false", "False"}

try:
    import pyttsx3

    _tts_engine = pyttsx3.init()
    _tts_engine.setProperty("rate", int(os.getenv("TTS_RATE", "175")))
    _tts_engine.setProperty("volume", float(os.getenv("TTS_VOLUME", "1.0")))

    def speak(text: str) -> None:
        if not TTS_ENABLED:
            return
        if not text or not text.strip():
            return
        _tts_engine.say(text)
        _tts_engine.runAndWait()

except Exception:
    # pyttsx3 설치/초기화 실패 시: TTS 끔 (텍스트 출력은 유지)
    TTS_ENABLED = False

    def speak(text: str) -> None:
        return


# =========================
# 데이터 구조
# =========================
@dataclass
class SensorState:
    temp: float
    humidity: float
    co2: float


@dataclass
class FarmStatus:
    level: str            # NORMAL / WARNING / CRITICAL
    reasons: list[str]    # 상태 원인
    action: str           # 권장 행동


@dataclass
class ConversationState:
    """DB 없이 메모리로만 유지하는 대화 상태"""
    pending: str | None = None               # 예: "VENTILATE_CONFIRM"
    last_intent: str | None = None
    history: deque = field(default_factory=lambda: deque(maxlen=10))  # (user, assistant)


# =========================
# 센서 → 상태 판단 (GPT 금지 영역)
# =========================
def analyze(state: SensorState) -> FarmStatus:
    reasons: list[str] = []
    level = "NORMAL"

    # 예시 기준 (원하면 GUI 설정값으로 바꿔도 됨)
    if state.co2 > 2500:
        level = "CRITICAL"
        reasons.append(f"CO₂ 높음 ({state.co2:.0f} ppm)")

    if state.temp > 30 and level != "CRITICAL":
        level = "WARNING"
        reasons.append(f"온도 높음 ({state.temp:.1f} ℃)")

    if level == "CRITICAL":
        action = "즉시 환기하고 팬을 가동하세요"
    elif level == "WARNING":
        action = "창문을 열거나 환기를 권장합니다"
    else:
        action = "현재 상태를 유지하세요"

    return FarmStatus(level=level, reasons=reasons, action=action)


# =========================
# 의도 분기 (룰 기반: 안정)
# =========================
def detect_intent(text: str) -> str:
    t = text.strip().lower()

    if any(k in t for k in ["상태", "어때", "괜찮", "요즘", "지금"]) :
        return "STATUS"
    if any(k in t for k in ["환기", "창문", "팬", "바람", "열어"]) :
        return "VENTILATION"
    if any(k in t for k in ["미션", "퀘스트", "게임"]) :
        return "MISSION"
    if any(k in t for k in ["농담", "재밌", "웃겨"]) :
        return "JOKE"

    return "CHAT"


def is_short_yes_no(text: str) -> bool:
    t = text.strip()
    return t in {"응", "네", "예", "ㅇㅇ", "어", "좋아", "그래", "아니", "아니요", "ㄴㄴ", "싫어", "노"}


# =========================
# 프롬프트 생성 (대화형: history + pending 포함)
# =========================
def build_prompt(user_text: str, status: FarmStatus, conv: ConversationState) -> str:
    history_text = "\n".join(
        [f"주인님: {u}\n{PLANT_NAME}: {a}" for (u, a) in conv.history]
    )

    pending_hint = ""
    if conv.pending == "VENTILATE_CONFIRM":
        pending_hint = (
            "너는 직전에 '환기할까요?' 라고 물었고, 사용자의 이번 발화는 그 질문에 대한 답일 수 있다. "
            "만약 사용자가 긍정(네/응/좋아)이면 '환기 시작'을 권하고, 부정이면 '대안' 1가지를 제시해라."
        )

    return f"""
너는 스마트팜 음성 비서가 아니라, '내가 직접 키우고 있는 식물'처럼 말하는 캐릭터다.
너의 정체는 '{PLANT_NAME}'이고, 1인칭으로 말한다. 사용자는 '주인님'이라고 부른다.

사실성 규칙(중요):
- 아래 상태/원인/권장 행동 범위를 벗어나는 사실을 만들어내지 않는다.
- 과장된 공포는 금지. 단, 귀엽게 걱정하는 표현은 허용.

말투/형식 규칙:
- 전체 2~3문장.
- 마지막 문장은 항상 상황 관련 농담 1문장(귀엽고 짧게).
- WARNING/CRITICAL일수록 더 짧고 행동을 앞에 둔다.
- 내부 규칙/정책을 설명하지 말고, 사용자에게 전달할 말만 출력한다.

[최근 대화]
{history_text if history_text else "(없음)"}

[현재 상태]
상태: {status.level}
원인 요약: {", ".join(status.reasons) if status.reasons else "특이사항 없음"}
권장 행동: {status.action}

[추가 힌트]
{pending_hint if pending_hint else "(없음)"}

[사용자 입력]
{user_text}

요청 의도: {detect_intent(user_text)}

응답을 한국어로 생성하라.
""".strip()


# =========================
# OpenAI 호출
# =========================
def call_openai(prompt: str, model: str = MODEL_NAME) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY가 설정되어 있지 않습니다 (.env 확인)")

    client = OpenAI(api_key=api_key)

    response = client.responses.create(
        model=model,
        instructions=(
            "너는 캐릭터(식물) 역할로 짧게 대답한다. "
            "센서 사실을 왜곡하지 말고, 2~3문장, 마지막은 농담 1문장."
        ),
        input=prompt,
    )

    return response.output_text.strip()


# =========================
# 데모 센서 입력 (나중에 실제 센서로 교체)
# =========================
def demo_sensor_read() -> SensorState:
    # TODO: 실제 센서 수신값으로 교체
    return SensorState(temp=37.2, humidity=55.0, co2=2600)


# =========================
# pending 상태 업데이트 (코드가 담당)
# =========================
def update_pending_after_answer(status: FarmStatus, answer: str, conv: ConversationState) -> None:
    """대화가 '이어지는 느낌'을 만들기 위해, 다음 턴의 기대 질문을 메모리로 저장."""
    # 간단 규칙: 위험하면 환기 여부를 물어보는 흐름
    if status.level in {"WARNING", "CRITICAL"}:
        # GPT가 꼭 질문을 출력하지 않더라도, 시스템이 pending을 잡아두면 다음 턴이 자연스러워짐
        conv.pending = "VENTILATE_CONFIRM"
    else:
        conv.pending = None


# =========================
# 한 턴 처리(입력 텍스트 -> 센서 반영 -> GPT -> TTS)
# =========================
def process_turn(user_text: str, conv: ConversationState) -> str:
    sensor = demo_sensor_read()
    status = analyze(sensor)

    prompt = build_prompt(user_text, status, conv)

    try:
        answer = call_openai(prompt)
        speak(answer)
    except Exception as e:
        answer = f"[오류] OpenAI 호출 실패: {e}"

    # 대화 기록 업데이트
    conv.history.append((user_text, answer))
    conv.last_intent = detect_intent(user_text)
    update_pending_after_answer(status, answer, conv)

    return answer


# =========================
# STT GUI 모드 (버튼 누르고 말하기)
# =========================
def run_stt_gui():
    if PushToTalkSTT is None:
        raise RuntimeError("example_STT.py의 PushToTalkSTT를 불러올 수 없습니다. example_STT.py가 같은 폴더에 있는지 확인하세요.")
    if tk is None:
        raise RuntimeError("Tkinter가 없어 GUI 버튼 모드를 사용할 수 없습니다. USE_STT_GUI=0 또는 Tk 포함 파이썬으로 실행하세요.")

    stt = PushToTalkSTT()
    conv = ConversationState()

    root = tk.Tk()
    root.title("AnyGrow2 - STT → GPT → TTS")
    root.geometry("680x360")

    status_var = tk.StringVar(value="버튼을 누르고 있는 동안 말하세요. (떼면 인식 후 답변)")
    stt_var = tk.StringVar(value="")
    ai_var = tk.StringVar(value="")

    lbl_status = tk.Label(root, textvariable=status_var, wraplength=640, justify="left")
    lbl_status.pack(pady=10)

    lbl_stt_title = tk.Label(root, text="인식 텍스트", font=("Arial", 11, "bold"))
    lbl_stt_title.pack()
    lbl_stt = tk.Label(root, textvariable=stt_var, wraplength=640, justify="left")
    lbl_stt.pack(pady=6)

    lbl_ai_title = tk.Label(root, text="AI 응답", font=("Arial", 11, "bold"))
    lbl_ai_title.pack()
    lbl_ai = tk.Label(root, textvariable=ai_var, wraplength=640, justify="left")
    lbl_ai.pack(pady=6)

    def on_press(_event=None):
        stt_var.set("")
        status_var.set("🎙️ 듣는 중... (버튼을 떼면 인식/응답)")
        stt.start_recording()

    def on_release(_event=None):
        status_var.set("🧠 인식 중...")

        def work():
            result = stt.stop_and_transcribe()
            text = (result.text or "").strip()
            if not text:
                status_var.set("❌ 인식 실패/무음. 다시 눌러서 말해보세요.")
                return

            stt_var.set(text)
            status_var.set("🤖 답변 생성 중...")

            answer = process_turn(text, conv)
            ai_var.set(answer)
            status_var.set("✅ 완료. 다시 누르고 말하세요.")

        threading.Thread(target=work, daemon=True).start()

    btn = tk.Button(root, text="누르고 말하기 (Push-to-talk)", width=40, height=3)
    btn.pack(pady=12)
    btn.bind("<ButtonPress-1>", on_press)
    btn.bind("<ButtonRelease-1>", on_release)

    # 스페이스도 지원
    root.bind("<KeyPress-space>", on_press)
    root.bind("<KeyRelease-space>", on_release)

    root.mainloop()


# =========================
# STT CLI 모드 (Tk 없이: Enter로 녹음 시작/종료)
# =========================
def run_stt_cli():
    if PushToTalkSTT is None:
        raise RuntimeError("example_STT.py의 PushToTalkSTT를 불러올 수 없습니다. example_STT.py가 같은 폴더에 있는지 확인하세요.")

    stt = PushToTalkSTT()
    conv = ConversationState()

    print("[AnyGrow2] STT CLI 모드입니다. (Tkinter 없음/비활성)")
    print("Enter -> 녹음 시작, Enter -> 녹음 종료/인식 후 답변, 종료: quit")

    while True:
        cmd = input("\n(Enter=녹음 시작, quit=종료)> ").strip().lower()
        if cmd in {"q", "quit", "exit"}:
            break

        print("🎙️ 녹음 중... (다시 Enter를 누르면 종료/인식)")
        stt.start_recording()
        input()

        print("🧠 인식 중...")
        result = stt.stop_and_transcribe()
        text = (result.text or "").strip()
        if not text:
            print("❌ 인식 실패/무음")
            continue

        print(f"STT> {text}")
        print("🤖 답변 생성 중...")
        answer = process_turn(text, conv)
        print(f"\nAI> {answer}\n")


# =========================
# 메인 루프 (STT 텍스트용)
# =========================
def main_loop():
    print("[AnyGrow2] STT 텍스트를 입력하면 센서 상태를 반영해 답변합니다. 종료: quit")
    if not TTS_ENABLED:
        print("[주의] TTS가 비활성입니다. (pyttsx3 설치/초기화 실패 또는 TTS_ENABLED=0)")

    conv = ConversationState()

    while True:
        user_text = input("STT> ").strip()
        if not user_text:
            continue
        if user_text.lower() in {"q", "quit", "exit"}:
            break

        # (텍스트 입력 모드) 한 턴 처리
        answer = process_turn(user_text, conv)
        print(f"\nAI> {answer}\n")


if __name__ == "__main__":
    if USE_STT:
        # GUI 선호지만 Tk가 없으면 CLI로 자동 폴백
        if USE_STT_GUI and tk is not None:
            run_stt_gui()
        else:
            run_stt_cli()
    else:
        main_loop()