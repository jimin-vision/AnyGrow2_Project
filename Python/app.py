# app.py
# AnyGrow2 Python 서버

from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import serial
import threading
import time

# -----------------------------
# 1. Flask & SocketIO 설정
# -----------------------------
app = Flask(__name__, static_folder='.', static_url_path='')
socketio = SocketIO(app, cors_allowed_origins="*")

# -----------------------------
# 2. 시리얼 포트 설정
# -----------------------------
SERIAL_PORT = 'COM5'   # 👉 여기만 나중에 실제 포트로 수정
BAUD_RATE = 38400

ser = None


def init_serial():
    global ser
    try:
        ser = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        print(f"[Serial] Opened {SERIAL_PORT} @ {BAUD_RATE}")
    except Exception as e:
        print("[Serial] Error opening port:", e)
        ser = None


# -----------------------------
# 3. 전역 상태값
# -----------------------------
packetLED = b""
reciving_data = b""

rq_state = ""    # "Off" / "Mood" / "On"
rc_state = "ok"  # "ok" / "wait"
receive_count = 0
data_state = ""

lock = threading.Lock()


# -----------------------------
# 4. 패킷 생성 함수
# -----------------------------
def make_led_packet(mode: str):
    if mode == "Off":
        hex_str = (
            "0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        )
    elif mode == "Mood":
        hex_str = (
            "0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        )
    elif mode == "On":
        hex_str = (
            "0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        )
    else:
        return None
    return bytes.fromhex(hex_str)


SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)


# -----------------------------
# 5. 웹 라우팅
# -----------------------------
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


@app.route("/<path:path>")
def static_proxy(path):
    return send_from_directory(".", path)


# -----------------------------
# 6. Socket.IO 이벤트
# -----------------------------
@socketio.on("connect")
def on_connect():
    print("[Socket] Client connected")


@socketio.on("disconnect")
def on_disconnect():
    print("[Socket] Client disconnected")


@socketio.on("serial_write")
def on_serial_write(data):
    global rq_state
    with lock:
        rq_state = data
    print(f"[Socket] serial_write: {data}")


@socketio.on("comm_state")
def on_comm_state(data):
    global rc_state, data_state, receive_count
    with lock:
        data_state = data
        rc_state = "ok"
        receive_count = 0
    print(f"[Socket] comm_state: {data}")


# -----------------------------
# 7. 1초 주기 루프
# -----------------------------
def background_loop():
    global rq_state, rc_state, receive_count

    while True:
        try:
            with lock:
                local_rq_state = rq_state
                local_rc_state = rc_state
                local_receive_count = receive_count

            if local_rc_state == "ok" and ser is not None:
                if local_rq_state != "":
                    led_packet = make_led_packet(local_rq_state)
                    if led_packet is not None:
                        print("@@@@@@@@@@ LED 제어 패킷 전송 @@@@@@@@@@")
                        print(led_packet)
                        ser.write(led_packet)
                    with lock:
                        rq_state = ""

                print("////////// 모니터링 센서데이터 요청 //////////")
                ser.write(SENSOR_REQUEST_PACKET)

                with lock:
                    rc_state = "wait"
                    receive_count = 0

            else:
                local_receive_count += 1
                if local_receive_count > 5:
                    print("[Loop] Timeout, rc_state 복구 → ok")
                    with lock:
                        rc_state = "ok"
                        receive_count = 0
                else:
                    with lock:
                        receive_count = local_receive_count

        except Exception as e:
            print("[Loop] Error:", e)

        time.sleep(1)


# -----------------------------
# 8. 시리얼 수신 루프
# -----------------------------
def serial_read_loop():
    global reciving_data

    if ser is None:
        print("[Serial] Port is not opened, skip read loop.")
        return

    while True:
        try:
            data = ser.read(1024)
            if data:
                reciving_data = data
                print(" - 센서데이터 수신")
                print(reciving_data)

                hex_string = data.hex()

                arr_reciveData = ""
                for i, ch in enumerate(hex_string):
                    if i != 0 and i % 2 == 0:
                        arr_reciveData += ","
                    arr_reciveData += ch

                socketio.emit("serial_recive", arr_reciveData)

        except Exception as e:
            print("[Serial] Read error:", e)

        time.sleep(0.05)


# -----------------------------
# 9. 메인 실행
# -----------------------------
if __name__ == "__main__":
    init_serial()

    loop_thread = threading.Thread(target=background_loop, daemon=True)
    loop_thread.start()

    serial_thread = threading.Thread(target=serial_read_loop, daemon=True)
    serial_thread.start()

    socketio.run(app, host="0.0.0.0", port=52273)
