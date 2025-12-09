# anygrow_gui.py
# AnyGrow2 순수 Python GUI (Tkinter + 시리얼)

import tkinter as tk
from tkinter import messagebox
import serial
import time

# -----------------------------
# 1. 시리얼 설정
# -----------------------------
SERIAL_PORT = "COM5"   # 👉 실제 포트
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
# 2. 패킷 정의 (기존 JS/Node와 동일)
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

# JS와 동일하게, 패킷 끝을 찾을 때 사용할 문자열
ETX = "ff,ff"          # anygrow2_client.js 의 var ETX='ff,ff'
packet_str = ""        # 수신 패킷 누적용 문자열

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
    if packet is None:
        return

    try:
        # LED 제어 + 최신 센서값 요청
        ser.write(packet)
        ser.write(SENSOR_REQUEST_PACKET)
        status_var.set(f"LED 명령 전송: {mode}")
    except Exception as e:
        status_var.set(f"[ERROR] LED 전송 실패: {e}")


# -----------------------------
# 4. JS hex2dec 그대로 포팅
#    (anygrow2_client.js 의 hex2dec 함수와 동일 로직)
# -----------------------------
def hex2dec(arr, first, last):
    """
    JS:

    function hex2dec(arr, first, last){
        var area = last-first;
        result = '';
        for(var i=first; i<=last; i++){
            result += String(eval(arr[i])-30);
        }
        return eval(result);
    }
    """
    result = ""
    for i in range(first, last + 1):
        # arr[i] 는 '30', '37' 같은 문자열
        # JS의 eval(arr[i])-30 과 동일하게 int(arr[i])-30 사용
        result += str(int(arr[i]) - 30)
    return int(result)


def parse_sensor_packet(arr):
    """
    JS에서 센서값을 뽑던 부분을 그대로 옮김:

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
        # 인덱스/값이 이상하면 None 리턴
        return None


# -----------------------------
# 5. 주기적 센서 폴링 + 패킷 파싱
# -----------------------------
def poll_serial():
    """
    - 1초마다 센서 요청 패킷 전송
    - 시리얼에서 들어온 데이터를 JS/Node와 동일한 방식으로
      ",로 구분된 문자열"로 만들고, ETX('ff,ff')가 들어오면
      완전한 패킷으로 보고 센서값 파싱
    """
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

        # 수신 데이터 읽기 (non-blocking)
        try:
            data = ser.read(1024)
            if data:
                # Node anygrow2_server.js 와 동일한 방식으로
                # reciving_data_hex -> arr_reciveData 문자열 생성
                reciving_data_hex = data.hex()    # 예: "0202ff53ff00..."
                part = ""
                for i, ch in enumerate(reciving_data_hex):
                    if (i % 2) == 0 and i != 0:
                        part += ","
                    part += ch

                # JS의 packet += data 와 동일
                packet_str += part
                raw_data_var.set(packet_str)

                # JS: if(packet.match(ETX)){ ... }
                if ETX in packet_str:
                    arr = packet_str.split(",")  # arr_reciveData 와 동일
                    parsed = parse_sensor_packet(arr)
                    if parsed is not None:
                        t, h, c, il = parsed
                        temp_var.set(f"{t:.1f} ℃")
                        hum_var.set(f"{h:.1f} %")
                        co2_var.set(f"{c} ppm")
                        illum_var.set(f"{il} lx")

                    # JS 처럼 패킷 처리 후 초기화
                    packet_str = ""

        except Exception as e:
            status_var.set(f"[ERROR] 수신 실패: {e}")

    # 200ms 후에 다시 호출
    root.after(200, poll_serial)


# -----------------------------
# 6. Tkinter GUI 구성
# -----------------------------
root = tk.Tk()
root.title("AnyGrow2 Python GUI")
root.geometry("800x450")

status_var = tk.StringVar(value="프로그램 시작")
raw_data_var = tk.StringVar(value="(아직 수신된 데이터 없음)")
request_counter_var = tk.StringVar(value="0")

temp_var = tk.StringVar(value="-")
hum_var = tk.StringVar(value="-")
co2_var = tk.StringVar(value="-")
illum_var = tk.StringVar(value="-")


# 상단: 상태 + 요청 횟수
top_frame = tk.Frame(root, padx=10, pady=10)
top_frame.pack(fill="x")

tk.Label(top_frame, text="시리얼 상태:", font=("Malgun Gothic", 10, "bold")).pack(side="left")
tk.Label(top_frame, textvariable=status_var).pack(side="left", padx=5)

tk.Label(top_frame, text="   센서 요청 횟수:", font=("Malgun Gothic", 10)).pack(side="left", padx=(20, 0))
tk.Label(top_frame, textvariable=request_counter_var).pack(side="left")


# LED 제어 버튼
btn_frame = tk.LabelFrame(root, text="LED 제어", padx=10, pady=10)
btn_frame.pack(fill="x", padx=10, pady=5)

tk.Button(btn_frame, text="OFF", width=10, command=lambda: send_led_command("Off")).pack(side="left", padx=5)
tk.Button(btn_frame, text="Mood", width=10, command=lambda: send_led_command("Mood")).pack(side="left", padx=5)
tk.Button(btn_frame, text="ON", width=10, command=lambda: send_led_command("On")).pack(side="left", padx=5)


# 센서값 표시
env_frame = tk.LabelFrame(root, text="센서값", padx=10, pady=10)
env_frame.pack(fill="x", padx=10, pady=5)

tk.Label(env_frame, text="온도:", width=10, anchor="w").grid(row=0, column=0, sticky="w")
tk.Label(env_frame, textvariable=temp_var).grid(row=0, column=1, sticky="w")

tk.Label(env_frame, text="습도:", width=10, anchor="w").grid(row=0, column=2, sticky="w")
tk.Label(env_frame, textvariable=hum_var).grid(row=0, column=3, sticky="w")

tk.Label(env_frame, text="CO₂:", width=10, anchor="w").grid(row=1, column=0, sticky="w")
tk.Label(env_frame, textvariable=co2_var).grid(row=1, column=1, sticky="w")

tk.Label(env_frame, text="조도:", width=10, anchor="w").grid(row=1, column=2, sticky="w")
tk.Label(env_frame, textvariable=illum_var).grid(row=1, column=3, sticky="w")


# RAW 패킷 문자열 표시 (디버깅용)
sensor_frame = tk.LabelFrame(root, text="센서 데이터 (수신 패킷 문자열)", padx=10, pady=10)
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
# 7. 메인 시작
# -----------------------------
if __name__ == "__main__":
    init_serial()
    root.after(200, poll_serial)
    root.mainloop()
