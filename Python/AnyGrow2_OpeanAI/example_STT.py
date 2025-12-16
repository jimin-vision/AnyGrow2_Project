"""Button-activated STT (Push-to-talk) demo.

- Hold the button (mouse down) to record.
- Release the button to stop, transcribe, and print the text.

Cross-platform (macOS/Windows) using:
- sounddevice (mic recording)
- faster-whisper (local transcription)

Install:
  pip install faster-whisper sounddevice numpy scipy

Notes:
- 첫 실행에서 마이크 권한을 요청할 수 있음.
- 기본 모델은 small. 느리면 base로 내리거나, 빠르게 하려면 tiny.
"""

import os
import queue
import tempfile
import threading
import time
try:
    import tkinter as tk
except Exception:  # Tk 미설치/미설정(특히 pyenv on macOS)
    tk = None
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel


# =========================
# STT 설정
# =========================
DEFAULT_MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")  # tiny/base/small/medium
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "auto")      # auto/cpu/cuda
WHISPER_COMPUTE = os.getenv("WHISPER_COMPUTE", "auto")   # auto/int8/float16
WHISPER_DOWNLOAD_ROOT = os.getenv(
    "WHISPER_DOWNLOAD_ROOT",
    os.path.join(os.path.dirname(__file__), ".whisper_models")
)
# 디코딩/지연 튜닝
BEAM_SIZE = int(os.getenv("WHISPER_BEAM", "1"))
BEST_OF = int(os.getenv("WHISPER_BEST_OF", "1"))
VAD_MIN_SILENCE_MS = int(os.getenv("VAD_MIN_SILENCE_MS", "250"))

# 정확도 튜닝 옵션
CONDITION_ON_PREV = os.getenv("CONDITION_ON_PREV", "0") in {"1", "true", "True"}
DECODE_TEMPERATURE = float(os.getenv("DECODE_TEMPERATURE", "0.0"))
PRINT_PRESET_HINT = os.getenv("PRINT_PRESET_HINT", "1") not in {"0", "false", "False"}

DEFAULT_DEVICE = os.getenv("AUDIO_DEVICE")  # None이면 기본 입력 장치
SAMPLE_RATE = int(os.getenv("AUDIO_SR", "16000"))
CHANNELS = 1


@dataclass
class STTResult:
    text: str
    language: str | None = None
    seconds: float | None = None


class PushToTalkSTT:
    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE):
        # faster-whisper 모델 로딩(초기 1회)
        # device="auto"로 두면 CPU/MPS/쿠다 환경에 맞춰 동작
        print(
            f"[STT] Loading WhisperModel size={model_size} device={WHISPER_DEVICE} compute={WHISPER_COMPUTE} "
            f"download_root={WHISPER_DOWNLOAD_ROOT} ..."
        )
        self.model = WhisperModel(model_size, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE, download_root=WHISPER_DOWNLOAD_ROOT)
        print("[STT] Model loaded")

        self._q: "queue.Queue[np.ndarray]" = queue.Queue()
        self._stream: sd.InputStream | None = None
        self._frames: list[np.ndarray] = []
        self._recording = False
        self._lock = threading.Lock()
        self._prev_text: str = ""  # 이전 턴 인식 텍스트(선택)

    def _callback(self, indata, frames, time_info, status):
        if status:
            # status는 디버깅용. 프린트가 싫으면 지워도 됨.
            pass
        # mono float32
        self._q.put(indata.copy())

    def start_recording(self):
        with self._lock:
            if self._recording:
                return
            self._recording = True
            self._frames = []

        # 큐 비우기
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            device=DEFAULT_DEVICE,
            callback=self._callback,
        )
        self._stream.start()

        # 프레임 수집 스레드
        threading.Thread(target=self._collector_loop, daemon=True).start()

    def _collector_loop(self):
        while True:
            with self._lock:
                if not self._recording:
                    break
            try:
                chunk = self._q.get(timeout=0.2)
                self._frames.append(chunk)
            except queue.Empty:
                continue

    def stop_and_transcribe(self) -> STTResult:
        with self._lock:
            if not self._recording:
                return STTResult(text="")
            self._recording = False

        # 스트림 정리
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None

        if not self._frames:
            return STTResult(text="")

        audio = np.concatenate(self._frames, axis=0).reshape(-1)

        # 너무 짧으면 의미 없는 경우 많음
        duration = len(audio) / float(SAMPLE_RATE)
        if duration < 0.25:
            return STTResult(text="", seconds=duration)

        # faster-whisper는 numpy audio(float32)도 바로 받을 수 있어서,
        # 파일 저장/읽기 오버헤드를 제거해 지연을 줄인다.
        audio_f32 = audio.astype(np.float32)

        print(f"[STT] Transcribing... (audio={duration:.2f}s, sr={SAMPLE_RATE}, beam={BEAM_SIZE})")
        t0 = time.time()
        segments, info = self.model.transcribe(
            audio_f32,
            language="ko",
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": VAD_MIN_SILENCE_MS},
            beam_size=BEAM_SIZE,
            best_of=BEST_OF,
            temperature=DECODE_TEMPERATURE,
            condition_on_previous_text=CONDITION_ON_PREV,
            initial_prompt=(self._prev_text[-200:] if (CONDITION_ON_PREV and self._prev_text) else None),
            without_timestamps=True,
        )
        print("[STT] Transcribe finished")
        text = "".join(seg.text for seg in segments).strip()
        if CONDITION_ON_PREV and text:
            # 너무 길어지지 않게 최근 일부만 유지
            self._prev_text = (self._prev_text + " " + text).strip()[-400:]
        dt = time.time() - t0

        return STTResult(text=text, language=getattr(info, "language", None), seconds=dt)


def run_tk_demo():
    stt = PushToTalkSTT()

    root = tk.Tk()
    root.title("AnyGrow2 - Push-to-talk STT")
    root.geometry("520x260")

    status_var = tk.StringVar(value="버튼을 누르고 있는 동안 말하세요. (떼면 인식)")
    out_var = tk.StringVar(value="")

    lbl_status = tk.Label(root, textvariable=status_var, wraplength=480, justify="left")
    lbl_status.pack(pady=10)

    txt_out = tk.Label(root, textvariable=out_var, wraplength=480, justify="left", font=("Arial", 12, "bold"))
    txt_out.pack(pady=10)

    def on_press(_event=None):
        out_var.set("")
        status_var.set("🎙️ 듣는 중... (버튼을 떼면 인식합니다)")
        stt.start_recording()

    def on_release(_event=None):
        status_var.set("🧠 인식 중...")

        def work():
            result = stt.stop_and_transcribe()
            if result.text:
                out_var.set(result.text)
                status_var.set(f"✅ 인식 완료 ({result.seconds:.2f}s)")
            else:
                out_var.set("")
                status_var.set("❌ 인식 실패/무음. 다시 눌러서 말해보세요.")

        threading.Thread(target=work, daemon=True).start()

    btn = tk.Button(root, text="누르고 말하기 (Push-to-talk)", width=36, height=3)
    btn.pack(pady=10)

    # 마우스 누름/떼기 이벤트
    btn.bind("<ButtonPress-1>", on_press)
    btn.bind("<ButtonRelease-1>", on_release)

    # 키보드 스페이스도 지원 (누르면 녹음, 떼면 인식)
    root.bind("<KeyPress-space>", on_press)
    root.bind("<KeyRelease-space>", on_release)

    root.mainloop()


def run_cli_demo():
    """Tk 없이도 동작하는 간단 데모.

    - Enter를 누르면 녹음 시작
    - 다시 Enter를 누르면 녹음 종료 + 인식
    """
    stt = PushToTalkSTT()
    print("[CLI STT] 첫 실행은 Whisper 모델을 다운로드하느라 오래 걸릴 수 있습니다. (인터넷 필요)")
    print("[CLI STT] Tkinter가 없어 CLI 모드로 실행합니다.")
    print("Enter -> 녹음 시작, Enter -> 녹음 종료/인식, 종료: quit")
    if PRINT_PRESET_HINT:
        print("\n[팁] 정확도 우선 프리셋 예시:")
        print("  export WHISPER_MODEL=small")
        print("  export WHISPER_DEVICE=cpu")
        print("  export WHISPER_COMPUTE=int8")
        print("  export WHISPER_BEAM=5")
        print("  export WHISPER_BEST_OF=5")
        print("  export VAD_MIN_SILENCE_MS=500")
        print("  export CONDITION_ON_PREV=1")
        print("  python example_STT.py\n")

    while True:
        cmd = input("\n(Enter=녹음 시작, quit=종료)> ").strip().lower()
        if cmd in {"q", "quit", "exit"}:
            break

        print("🎙️ 녹음 중... (다시 Enter를 누르면 종료/인식)")
        stt.start_recording()
        input()

        print("🧠 인식 중...")
        result = stt.stop_and_transcribe()
        if result.text:
            print(f"✅ 인식: {result.text}  (t={result.seconds:.2f}s)")
        else:
            print("❌ 인식 실패/무음")


if __name__ == "__main__":
    if tk is None:
        run_cli_demo()
    else:
        run_tk_demo()