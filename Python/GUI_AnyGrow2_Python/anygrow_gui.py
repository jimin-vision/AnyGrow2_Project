# anygrow_gui.py
# AnyGrow2 순수 Python GUI (Tkinter + 시리얼)

import tkinter as tk
from tkinter import messagebox
import serial
import time

# -----------------------------
# 1. 시리얼 설정
# -----------------------------
SERIAL_PORT = "COM5"   # 👉 실제 보드가 연결된 포트로 맞춰줘
BAUD_RATE = 38400

ser = None

def init_serial():
    """시리얼 포트를 연다."""
    global ser
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0,   # non-blocking read
        )
        status_var.set(f"[OK] 포트 {SERIAL_PORT} @ {BAUD_RATE} 연결됨")
    except Exception as e:
        ser = None
        status_var.set(f"[ERROR] 시리얼 오픈 실패: {e}")
        messagebox.showerror("Serial Error", f"시리얼 포트를 열 수 없습니다.\n{e}")

# -----------------------------
# 2. 패킷 정의 (Node / app.py 와 동일)
# -----------------------------
LED_PACKETS = {
    "Off": bytes.fromhex(
        "0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    ),
    "Mood": bytes.fromhex(
        "0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    ),
    "On": bytes.fromhex(
        "0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    ),
}

SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)

last_sensor_request_time = 0.0


# -----------------------------
# 3. LED 제어 함수
# -----------------------------
def send_led_command(mode: str):
    """LED Off/Mood/On 명령을 보낸다."""
    if ser is None or not ser.is_open:
        messagebox.showwarning("Serial", "시리얼 포트가 열려 있지 않습니다.")
        return

    packet = LED_PACKETS.get(mode)
    if packet is None:asd
        return

    try:
        ser.write(packet)                 # LED 제어
        ser.write(SENSOR_REQUEST_PACKET)  # 최신 센서값도 함께 요청
        status_var.set(f"LED 명령 전송: {mode}")
    except Exception as e:
        status_var.set(f"[ERROR] LED 전송 실패: {e}")


# -----------------------------
# 4. 주기적 센서 폴링
# -----------------------------
def poll_serial():
    """
    Tkinter 메인 쓰레드에서 주기적으로 호출.
    - 1초에 한 번 센서 요청 패킷 전송
    - 들어온 센서데이터를 화면에 표시
    """
    global last_sensor_request_time

    if ser is not None and ser.is_open:
        now = time.time()

        # 1초마다 센서 요청
        if now - last_sensor_request_time >= 1.0:
            try:
                ser.write(SENSOR_REQUEST_PACKET)
                last_sensor_request_time = now
                # 로그 표시
                request_count = int(request_counter_var.get() or "0") + 1
                request_counter_var.set(str(request_count))
            except Exception as e:
                status_var.set(f"[ERROR] 센서 요청 실패: {e}")

        # 수신 데이터 읽기 (non-blocking)
        try:
            data = ser.read(1024)
            if data:
                # 원시 바이트를 "aa bb cc ..." 형식의 hex 문자열로 변환
                hex_str = data.hex(" ")
                raw_data_var.set(hex_str)

                # TODO: 나중에 여기서 실제 온도/습도/CO2/조도 값으로 파싱해서
                #       아래 라벨들에 숫자를 넣어줄 수 있음.
                # 현재는 먼저 "파이썬만으로 통신/GUI"가 되는지 확인하는 단계.

        except Exception as e:
            status_var.set(f"[ERROR] 수신 실패: {e}")

    # 200ms 후에 다시 자기 자신을 호출
    root.after(200, poll_serial)


# -----------------------------
# 5. Tkinter GUI 설정
# -----------------------------
root = tk.Tk()
root.title("AnyGrow2 Python GUI")

# 글자 크기/여백 통일을 위해 기본 폰트 키우고 패딩 주기
root.geometry("800x400")

status_var = tk.StringVar(value="프로그램 시작")
raw_data_var = tk.StringVar(value="(아직 수신된 데이터 없음)")
request_counter_var = tk.StringVar(value="0")

# 상단 프레임: 연결 상태 + 요청 횟수
top_frame = tk.Frame(root, padx=10, pady=10)
top_frame.pack(fill="x")

tk.Label(top_frame, text="시리얼 상태:", font=("Malgun Gothic", 10, "bold")).pack(side="left")
tk.Label(top_frame, textvariable=status_var).pack(side="left", padx=5)

tk.Label(top_frame, text="   센서 요청 횟수:", font=("Malgun Gothic", 10)).pack(side="left", padx=(20, 0))
tk.Label(top_frame, textvariable=request_counter_var).pack(side="left")

# 가운데 프레임: LED 제어 버튼
btn_frame = tk.LabelFrame(root, text="LED 제어", padx=10, pady=10)
btn_frame.pack(fill="x", padx=10, pady=5)

btn_off = tk.Button(btn_frame, text="OFF", width=10, command=lambda: send_led_command("Off"))
btn_mood = tk.Button(btn_frame, text="Mood", width=10, command=lambda: send_led_command("Mood"))
btn_on = tk.Button(btn_frame, text="ON", width=10, command=lambda: send_led_command("On"))

btn_off.pack(side="left", padx=5)
btn_mood.pack(side="left", padx=5)
btn_on.pack(side="left", padx=5)

# 하단 프레임: 센서 데이터 표시 (현재는 raw hex)
sensor_frame = tk.LabelFrame(root, text="센서 데이터 (RAW HEX)", padx=10, pady=10)
sensor_frame.pack(fill="both", expand=True, padx=10, pady=5)

sensor_text = tk.Label(
    sensor_frame,
    textvariable=raw_data_var,
    anchor="nw",
    justify="left",
    wraplength=760,
)
sensor_text.pack(fill="both", expand=True)

# 종료 처리
def on_close():
    try:
        if ser is not None and ser.is_open:
            ser.close()
    except Exception:
        pass
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_close)

# -----------------------------
# 6. 메인 시작
# -----------------------------
if __name__ == "__main__":
    init_serial()
    # 주기적 폴링 시작
    root.after(200, poll_serial)
    root.mainloop()
