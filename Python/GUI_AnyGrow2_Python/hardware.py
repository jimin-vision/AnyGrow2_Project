# hardware.py
# AnyGrow2 보드와 시리얼 통신 + 센서 데이터 파싱 + LED 제어

import serial
import time
import threading

# -----------------------------
# 시리얼 설정
# -----------------------------
SERIAL_PORT = "COM5"     # 필요하면 여기만 바꾸면 됨
BAUD_RATE = 38400

ser = None
port_lock = threading.Lock()

# 센서 요청 패킷 (app.py에서 쓰던 것과 동일)
SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)

# LED 제어 패킷 (Off / Mood / On)
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

# -----------------------------
# 내부 상태
# -----------------------------
_last_raw_string = "(아직 수신된 데이터 없음)"
_last_reading = None      # (temp, hum, co2, illum)

_request_counter = 0                  # 센서 요청 보낸 횟수
_last_poll_seen_request_counter = 0   # GUI에서 마지막으로 확인한 값

_running = False


# -----------------------------
# 헬퍼: 센서 데이터 파싱
# -----------------------------
def _hex_list_from_bytes(data: bytes):
    """바이트 → ['02','02','ff',...] 형식 리스트"""
    hex_string = data.hex()  # '0202ff53...'
    arr = []
    for i in range(0, len(hex_string), 2):
        arr.append(hex_string[i:i+2])
    return arr


def _hex2dec(arr, first, last):
    """
    anygrow2_client.js의 hex2dec와 동일한 로직
    arr[first]~arr[last]에 저장된 '30','31',... 값을
    각 자리에서 0x30을 빼서 숫자로 이어붙인 뒤 정수로 변환
    """
    result = ""
    for i in range(first, last + 1):
        v = int(arr[i], 16) - 0x30
        if not (0 <= v <= 9):
            return None
        result += str(v)
    if not result:
        return None
    return int(result)


def _parse_sensor_packet(arr):
    """
    arr: ['02','02','ff',...,'ff','ff','03'] (길이 30 가정)
    anygrow2_client.js 기준:
      - arr[1] == "02" → 센서 데이터
      - 온도:  hex2dec(arr,10,12) / 10
      - 습도:  hex2dec(arr,14,16) / 10
      - CO2:   hex2dec(arr,18,21)
      - 조도:  hex2dec(arr,23,26)
    """
    if len(arr) < 30:
        return None
    # 뒤에서 30바이트만 사용 (중간에 쓰레기 끼어도 마지막 패킷 보려고)
    arr = arr[-30:]
    if arr[1] != "02":
        return None

    t_raw = _hex2dec(arr, 10, 12)
    h_raw = _hex2dec(arr, 14, 16)
    c_raw = _hex2dec(arr, 18, 21)
    i_raw = _hex2dec(arr, 23, 26)

    if None in (t_raw, h_raw, c_raw, i_raw):
        return None

    temp = t_raw / 10.0
    hum = h_raw / 10.0
    co2 = c_raw
    illum = i_raw
    return (temp, hum, co2, illum)


# -----------------------------
# 시리얼 초기화 & close
# -----------------------------
def init_serial():
    """포트 열고, 요청 스레드 + 수신 스레드 시작"""
    global ser, _running, _request_counter
    with port_lock:
        ser_local = serial.Serial(
            port=SERIAL_PORT,
            baudrate=BAUD_RATE,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.1,
        )
        ser = ser_local

    _running = True
    _request_counter = 0

    t_req = threading.Thread(target=_request_loop, daemon=True)
    t_req.start()

    t_read = threading.Thread(target=_read_loop, daemon=True)
    t_read.start()


def close_serial():
    global ser, _running
    _running = False
    with port_lock:
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
            ser = None


# -----------------------------
# 백그라운드: 1초마다 센서 요청 보내기
# -----------------------------
def _request_loop():
    global _request_counter
    while _running:
        with port_lock:
            ser_local = ser
        if ser_local is None:
            break

        try:
            ser_local.write(SENSOR_REQUEST_PACKET)
            _request_counter += 1
        except Exception as e:
            print("[Serial] SENSOR_REQUEST write error:", e)

        time.sleep(1.0)


# -----------------------------
# 백그라운드: 계속 읽어서 마지막 패킷 보관
# -----------------------------
def _read_loop():
    global _last_raw_string, _last_reading
    while _running:
        with port_lock:
            ser_local = ser
        if ser_local is None:
            break

        try:
            data = ser_local.read(1024)
        except Exception as e:
            print("[Serial] read error:", e)
            time.sleep(0.2)
            continue

        if data:
            arr = _hex_list_from_bytes(data)
            raw_string = ",".join(arr)
            _last_raw_string = raw_string

            reading = _parse_sensor_packet(arr)
            if reading is not None:
                _last_reading = reading

        time.sleep(0.02)


# -----------------------------
# GUI에서 주기적으로 호출하는 함수
# -----------------------------
def poll_sensor_once():
    """
    GUI의 poll_serial()에서 호출.
    여기서는 단순히:
      - 스레드가 보관 중인 마지막 reading/raw를 가져와서 돌려줌
      - 요청 스레드가 새 패킷을 보냈는지 여부만 알려줌
    return: (reading, raw_string, request_sent)
      - reading: (temp, hum, co2, illum) 또는 None
      - raw_string: "02,02,ff,..." 형식 문자열
      - request_sent: 마지막 poll 이후 센서 요청을 최소 1번 보냈으면 True
    """
    global _last_poll_seen_request_counter

    with port_lock:
        ser_local = ser
    if ser_local is None:
        return None, "시리얼 포트가 열려있지 않습니다.", False

    reading_copy = _last_reading
    raw_copy = _last_raw_string

    # 요청 카운터 비교해서 변화 있으면 True
    current = _request_counter
    if current != _last_poll_seen_request_counter:
        request_sent = True
        _last_poll_seen_request_counter = current
    else:
        request_sent = False

    return reading_copy, raw_copy, request_sent


# -----------------------------
# LED 제어
# -----------------------------
def send_led_packet(mode: str):
    """
    mode: "Off" / "Mood" / "On"
    """
    with port_lock:
        ser_local = ser

    if ser_local is None:
        raise RuntimeError("시리얼 포트가 열려있지 않습니다.")

    packet = LED_PACKETS.get(mode)
    if packet is None:
        raise ValueError(f"Unknown LED mode: {mode}")

    ser_local.write(packet)


# -----------------------------
# RGB 라인 제어 (현재는 디버그 출력만)
# -----------------------------
def apply_rgb_state(lines):
    """
    lines: [
      {"index": 1..7, "enabled": bool, "mode": "Off/Mood/On", "color": "#rrggbb"},
      ...
    ]

    아직 AnyGrow2 RGB 세부 프로토콜이 파악되지 않아서
    실제 조명 제어 대신 콘솔 로그만 남김.
    나중에 프로토콜을 알게 되면 이 함수 안에서
    ser.write(...)로 패킷을 보내도록 구현하면 됨.
    """
    print("[RGB] apply_rgb_state 호출 (현재는 로그만 출력)")
    for line in lines:
        print(
            f"  line {line['index']}: "
            f"enabled={line['enabled']}, mode={line['mode']}, color={line['color']}"
        )
