# anygrow_gui.py
# AnyGrow2 순수 Python GUI (Tkinter + 시리얼 + 간단 그래프/알림)

import tkinter as tk
from tkinter import messagebox
import serial
import time
from datetime import datetime

# -----------------------------
# 1. 시리얼 설정
# -----------------------------
SERIAL_PORT = "COM5"   # 👉 실제 보드 포트
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
# 2. 패킷 정의 (JS/Node와 동일)
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

# 센서 데이터 요청 패킷
SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)

# anygrow2_client.js 와 동일하게 사용
ETX = "ff,ff"
packet_str = ""        # 수신 패킷 누적용 문자열

last_sensor_request_time = 0.0


# -----------------------------
# 3. LED 제어
# -----------------------------
def send_led_command(mode: str):
    """LED Off/Mood/On 명령을 보낸다."""
    if ser is None or not ser.is_open:
        messagebox.showwarning("Serial", "시리얼 포트가 열려 있지 않습니다.")
        return

    packet = LED_PACKETS.get(mode)
    if packet is None:
        return

    try:
        ser.write(packet)
        ser.write(SENSOR_REQUEST_PACKET)  # 최신 센서값 요청
        status_var.set(f"LED 명령 전송: {mode}")
    except Exception as e:
        status_var.set(f"[ERROR] LED 전송 실패: {e}")


# -----------------------------
# 4. JS hex2dec 포팅
# -----------------------------
def hex2dec(arr, first, last):
    """
    JS:

    function hex2dec(arr, first, last){
        result='';
        for(i=first;i<=last;i++){ result += String(eval(arr[i])-30); }
        return eval(result);
    }
    """
    result = ""
    for i in range(first, last + 1):
        result += str(int(arr[i]) - 30)
    return int(result)


def parse_sensor_packet(arr):
    """
    JS 코드:

    if(arr_reciveData.length==30){
      if(arr_reciveData[1]=="02"){
        arrEnv[0][0] = hex2dec(arr_reciveData,10,12)/10; // 온도
        arrEnv[1][0] = hex2dec(arr_reciveData,14,16)/10; // 습도
        arrEnv[2][0] = hex2dec(arr_reciveData,18,21);    // CO2
        arrEnv[3][0] = hex2dec(arr_reciveData,23,26);    // 조도
      }
    }
    """
    if len(arr) != 30:
        return None
    if arr[1] != "02":
        return None

    try:
        temperature = hex2dec(arr, 10, 12) / 10.0
        humidity = hex2dec(arr, 14, 16) / 10.0
        co2 = hex2dec(arr, 18, 21)
        illumination = hex2dec(arr, 23, 26)
        return temperature, humidity, co2, illumination
    except Exception:
        return None


# -----------------------------
# 5. 간단 그래프(막대) 업데이트
# -----------------------------
# 막대를 그릴 때 사용할 최대값 (대충 일반적인 범위로 설정)
MAX_TEMP = 40.0      # ℃
MAX_HUM = 100.0      # %
MAX_CO2 = 2000.0     # ppm
MAX_ILLUM = 5000.0   # lx

BAR_WIDTH = 220
BAR_HEIGHT = 18

bar_widgets = {}  # sensor_name -> (canvas, rect_id)


def create_bar(parent, row, label_text, var):
    """한 줄짜리 라벨 + 값 + 막대 그래프 생성."""
    tk.Label(parent, text=label_text, width=8, anchor="w").grid(
        row=row, column=0, sticky="w"
    )
    value_label = tk.Label(parent, textvariable=var, width=12, anchor="w")
    value_label.grid(row=row, column=1, sticky="w")

    canvas = tk.Canvas(parent, width=BAR_WIDTH, height=BAR_HEIGHT, highlightthickness=1)
    canvas.grid(row=row, column=2, sticky="w", padx=(10, 0))
    rect = canvas.create_rectangle(0, 0, 0, BAR_HEIGHT, fill="#4caf50")
    return canvas, rect, value_label


def get_bar_color(sensor, value):
    """값에 따라 색상(정상/주의/위험) 결정."""
    # 기본 threshold는 대략적인 값. 나중에 조정 가능.
    if sensor == "temp":
        if value < 15 or value > 30:
            return "#f44336"  # 빨강 (너무 낮거나 높음)
        elif 15 <= value <= 18 or 27 <= value <= 30:
            return "#ff9800"  # 주의
        else:
            return "#4caf50"  # 정상
    elif sensor == "hum":
        if value < 30 or value > 80:
            return "#f44336"
        elif 30 <= value <= 40 or 70 <= value <= 80:
            return "#ff9800"
        else:
            return "#4caf50"
    elif sensor == "co2":
        if value > 1500:
            return "#f44336"
        elif value > 1000:
            return "#ff9800"
        else:
            return "#4caf50"
    elif sensor == "illum":
        # 값이 너무 낮으면 빨강, 애매하면 주황, 충분하면 초록
        if value < 200:
            return "#f44336"
        elif value < 800:
            return "#ff9800"
        else:
            return "#4caf50"
    return "#4caf50"


def update_sensor_bars(t, h, c, il):
    """막대 그래프와 라벨 색상 업데이트."""
    # 각 센서별 최대값 대비 비율
    values = {
        "temp": (t, MAX_TEMP),
        "hum": (h, MAX_HUM),
        "co2": (c, MAX_CO2),
        "illum": (il, MAX_ILLUM),
    }

    for name, (value, max_val) in values.items():
        canvas, rect, label = bar_widgets[name]
        ratio = max(0.0, min(1.0, value / max_val))
        width = int(ratio * BAR_WIDTH)
        color = get_bar_color(name, value)

        canvas.coords(rect, 0, 0, width, BAR_HEIGHT)
        canvas.itemconfig(rect, fill=color)
        label.config(fg=color)


# -----------------------------
# 6. 주기적 센서 폴링 + 파싱
# -----------------------------
def poll_serial():
    global last_sensor_request_time, packet_str

    if ser is not None and ser.is_open:
        now = time.time()

        # 1초마다 센서 요청
        if now - last_sensor_request_time >= 1.0:
            try:
                ser.write(SENSOR_REQUEST_PACKET)
                last_sensor_request_time = now
                req_cnt = int(request_counter_var.get() or "0") + 1
                request_counter_var.set(str(req_cnt))
            except Exception as e:
                status_var.set(f"[ERROR] 센서 요청 실패: {e}")

        # 수신 읽기
        try:
            data = ser.read(1024)
            if data:
                reciving_data_hex = data.hex()  # "0202ff53ff00..."
                part = ""
                for i, ch in enumerate(reciving_data_hex):
                    if i != 0 and i % 2 == 0:
                        part += ","
                    part += ch

                packet_str += part
                raw_data_var.set(packet_str)  # 디버깅용 표시

                # 패킷 끝(ETX) 확인
                if ETX in packet_str:
                    arr = packet_str.split(",")
                    parsed = parse_sensor_packet(arr)
                    if parsed is not None:
                        t, h, c, il = parsed
                        temp_var.set(f"{t:.1f} ℃")
                        hum_var.set(f"{h:.1f} %")
                        co2_var.set(f"{c} ppm")
                        illum_var.set(f"{il} lx")

                        # 그래프/색깔 업데이트
                        update_sensor_bars(t, h, c, il)

                        # 마지막 갱신 시각
                        last_update_var.set(
                            datetime.now().strftime("마지막 갱신: %Y-%m-%d %H:%M:%S")
                        )
                    packet_str = ""

        except Exception as e:
            status_var.set(f"[ERROR] 수신 실패: {e}")

    root.after(200, poll_serial)


# -----------------------------
# 7. Tkinter GUI
# -----------------------------
root = tk.Tk()
root.title("AnyGrow2 Python GUI")
root.geometry("860x520")

status_var = tk.StringVar(value="프로그램 시작")
raw_data_var = tk.StringVar(value="(아직 수신된 데이터 없음)")
request_counter_var = tk.StringVar(value="0")

temp_var = tk.StringVar(value="-")
hum_var = tk.StringVar(value="-")
co2_var = tk.StringVar(value="-")
illum_var = tk.StringVar(value="-")
last_update_var = tk.StringVar(value="마지막 갱신: -")


# 상단 상태 바
top_frame = tk.Frame(root, padx=10, pady=10)
top_frame.pack(fill="x")

tk.Label(top_frame, text="시리얼 상태:", font=("Malgun Gothic", 10, "bold")).pack(side="left")
tk.Label(top_frame, textvariable=status_var).pack(side="left", padx=5)

tk.Label(top_frame, text="   센서 요청 횟수:", font=("Malgun Gothic", 10)).pack(
    side="left", padx=(20, 0)
)
tk.Label(top_frame, textvariable=request_counter_var).pack(side="left")


# LED 제어
btn_frame = tk.LabelFrame(root, text="LED 제어", padx=10, pady=10)
btn_frame.pack(fill="x", padx=10, pady=5)

tk.Button(btn_frame, text="OFF", width=10, command=lambda: send_led_command("Off")).pack(
    side="left", padx=5
)
tk.Button(btn_frame, text="Mood", width=10, command=lambda: send_led_command("Mood")).pack(
    side="left", padx=5
)
tk.Button(btn_frame, text="ON", width=10, command=lambda: send_led_command("On")).pack(
    side="left", padx=5
)


# 센서값 + 그래프
env_frame = tk.LabelFrame(root, text="센서값", padx=10, pady=10)
env_frame.pack(fill="x", padx=10, pady=5)

# 숫자 + 막대 그래프 한 줄씩
temp_canvas, temp_rect, temp_label = create_bar(env_frame, 0, "온도", temp_var)
hum_canvas, hum_rect, hum_label = create_bar(env_frame, 1, "습도", hum_var)
co2_canvas, co2_rect, co2_label = create_bar(env_frame, 2, "CO₂", co2_var)
illum_canvas, illum_rect, illum_label = create_bar(env_frame, 3, "조도", illum_var)

bar_widgets["temp"] = (temp_canvas, temp_rect, temp_label)
bar_widgets["hum"] = (hum_canvas, hum_rect, hum_label)
bar_widgets["co2"] = (co2_canvas, co2_rect, co2_label)
bar_widgets["illum"] = (illum_canvas, illum_rect, illum_label)

# 마지막 갱신 시간
tk.Label(env_frame, textvariable=last_update_var).grid(
    row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
)


# RAW 패킷 표시 (디버깅용)
sensor_frame = tk.LabelFrame(root, text="센서 데이터 (수신 패킷 문자열)", padx=10, pady=10)
sensor_frame.pack(fill="both", expand=True, padx=10, pady=5)

sensor_text = tk.Label(
    sensor_frame,
    textvariable=raw_data_var,
    anchor="nw",
    justify="left",
    wraplength=820,
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
# 8. 메인 시작
# -----------------------------
if __name__ == "__main__":
    init_serial()
    root.after(200, poll_serial)
    root.mainloop()
