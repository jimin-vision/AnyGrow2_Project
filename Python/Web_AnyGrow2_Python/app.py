# app.py
# AnyGrow2 Python 서버 (Flask + Socket.IO + 시리얼)

from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import serial
import threading
import time

# -----------------------------
# 1. Flask & SocketIO 설정
# -----------------------------
# static_folder='.' : 현재 폴더에서 index.html, js, css, image 를 그대로 서빙
app = Flask(__name__, static_folder='.', static_url_path='')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# -----------------------------
# 2. 시리얼 포트 설정
# -----------------------------
SERIAL_PORT = 'COM5'   # 👉 실제 연결된 포트로 수정
BAUD_RATE = 38400

ser = None


def init_serial():
    """
    시리얼 포트 오픈
    """
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
# 3. 전역 상태값 (Node 서버와 동일 구조)
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
        hex_str = "0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    elif mode == "Mood":
        hex_str = "0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    elif mode == "On":
        hex_str = "0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    else:
        return None
    return bytes.fromhex(hex_str)


# 센서 데이터 요청 패킷 (Node 코드의 0202FF53... 동일)
SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)


# -----------------------------
# 5. 웹 라우팅
# -----------------------------
@app.route("/")
def index():
    # ./index.html 그대로 반환
    return send_from_directory(".", "index.html")


@app.route("/<path:path>")
def static_proxy(path):
    # ./ 이하의 모든 정적 파일(js, css, image 등) 서빙
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
    """
    클라이언트(anygrow2_client.js)에서
    socket.emit('serial_write', "On") 이런 식으로 보내는 이벤트.
    여기서는 rq_state 에 저장만 하고,
    실제 패킷 전송은 background_loop 에서 1초 주기로 처리.
    """
    global rq_state
    print(f"[Socket] serial_write: {data}")
    with lock:
        rq_state = data   # "Off" / "Mood" / "On"


@socketio.on("comm_state")
def on_comm_state(data):
    """
    클라이언트가 센서 데이터 처리를 끝냈다고 알려주는 이벤트.
    타임아웃(통신 끊김) 체크에 사용.
    anygrow2_client.js 에서 socket.emit('comm_state', 'sensor data response')
    """
    global rc_state, data_state, receive_count
    print(f"[Socket] comm_state: {data}")
    with lock:
        data_state = data
        rc_state = "ok"
        receive_count = 0


# -----------------------------
# 7. 1초 주기 루프 (LED 제어 + 센서 요청)
# -----------------------------
def background_loop():
    global rq_state, rc_state, receive_count

    while True:
        try:
            with lock:
                local_rq_state = rq_state
                local_rc_state = rc_state
                local_receive_count = receive_count

            if ser is not None and local_rc_state == "ok":
                # 1) LED 제어 요청이 있으면 먼저 처리
                if local_rq_state != "":
                    led_packet = make_led_packet(local_rq_state)
                    if led_packet is not None:
                        print("@@@@@@@@@@ LED 제어 패킷 전송 @@@@@@@@@@")
                        print(led_packet)
                        try:
                            ser.write(led_packet)
                        except Exception as e:
                            print("[Loop] LED write error:", e)
                    # 한번 처리한 뒤에는 rq_state 비우기
                    with lock:
                        rq_state = ""

                # 2) 그 다음 센서 데이터 요청
                try:
                    print("////////// 모니터링 센서데이터 요청 //////////")
                    ser.write(SENSOR_REQUEST_PACKET)
                except Exception as e:
                    print("[Loop] Sensor request write error:", e)

                with lock:
                    rc_state = "wait"
                    receive_count = 0

            else:
                # 응답 대기 중이면 타임아웃 카운트
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

                # Node 서버처럼: 수신된 바이트를 hex string -> "aa,bb,cc,..." 형식으로 변환
                hex_string = data.hex()
                arr_reciveData = ""
                for i, ch in enumerate(hex_string):
                    if i != 0 and i % 2 == 0:
                        arr_reciveData += ","
                    arr_reciveData += ch

                # 소켓으로 클라이언트에 전달
                socketio.emit("serial_recive", arr_reciveData)
        except Exception as e:
            print("[Serial] Read error:", e)

        time.sleep(0.05)


# -----------------------------
# 9. 메인 실행
# -----------------------------
if __name__ == "__main__":
    init_serial()

    # 백그라운드 쓰레드 시작
    loop_thread = threading.Thread(target=background_loop, daemon=True)
    loop_thread.start()

    serial_thread = threading.Thread(target=serial_read_loop, daemon=True)
    serial_thread.start()

    # Flask + Socket.IO 서버 실행
    socketio.run(app, host="0.0.0.0", port=52273)
