# hardware.py
# AnyGrow2 보드와 시리얼 통신 + 센서 데이터 파싱 + LED/펌프/UV + (자리만 잡아 둔) 밝기 제어

import serial
import time
import threading

# -----------------------------
# 시리얼 설정
# -----------------------------
SERIAL_PORT = "COM5"   # 필요하면 여기만 수정
BAUD_RATE = 38400

ser = None
port_lock = threading.Lock()

# 센서 요청 패킷
#  - AnyGrow 프로토콜 엑셀 기준:
#    STX(0x02), MODE(0x02:센서보드), CMD('S' = 0x53), CH(0x00), 나머지 0xFF, ETX(0x03)
SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)

# LED 제어 패킷 (전체 On / Mood / Off)
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

# 양액 펌프 / UV 필터 제어 패킷
# ❗ 아직 정확한 HEX를 모름 → 알게 되면 아래 네 변수를 채우면 됨
PUMP_ON_PACKET = None
PUMP_OFF_PACKET = None

UV_ON_PACKET = None
UV_OFF_PACKET = None

# BMS 재부팅 패킷
# ❗ AnyGrow 프로토콜에 BMS 재부팅 명령이 명시적으로 없어 임의로 정의함
#    - MODE: 0x04 (LED=0x01, SENSOR=0x02 이므로 충돌 피해서)
#    - CMD:  'R' = 0x52
BMS_REBOOT_PACKET = bytes.fromhex(
    "0204FF52FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)


# -----------------------------
# 내부 상태
# -----------------------------
_last_raw_string = "(아직 수신된 데이터 없음)"
_last_reading = None        # (temp, hum, co2, illum)
_last_read_time = None      # 마지막 유효 센서 패킷 수신 시각 (epoch sec)

_request_counter = 0                  # 센서 요청 보낸 횟수
_last_poll_seen_request_counter = 0   # GUI에서 마지막으로 확인한 값

_running = False


# -----------------------------
# 헬퍼: 센서 데이터 파싱
# -----------------------------
def _hex_list_from_bytes(data: bytes):
    """바이트 → ['02','02','ff', ...] 형식 리스트"""
    hex_string = data.hex()
    arr = []
    for i in range(0, len(hex_string), 2):
        arr.append(hex_string[i:i+2])
    return arr


def _hex2dec(arr, first, last):
    """
    anygrow2_client.js 의 hex2dec 와 동일한 로직.

    arr[first]~arr[last] 에 저장된 '30','31' 같은 값을
    각 자리에서 0x30 을 빼서 숫자로 바꾼 뒤 문자열로 붙이고 int 로 변환.
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
    arr: ['02','02','ff', ...] (길이 30 가정)

    AnyGrow 센서 데이터 패킷 구조 (엑셀 기준):
      - arr[1] == "02" → 센서 데이터
      - 온도:  hex2dec(arr,10,12) / 10
      - 습도:  hex2dec(arr,14,16) / 10
      - CO2:   hex2dec(arr,18,21)
      - 조도:  hex2dec(arr,23,26)
    """
    if len(arr) < 30:
        return None

    # 뒤에서 30바이트만 사용 (중간에 쓰레기 끼어도 마지막 패킷을 보려고)
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
    """포트 열고, 요청 스레드 + 수신 스레드 시작."""
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

    _running = True    # 스레드 루프 ON
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
            if ser is None:
                break
            try:
                ser.write(SENSOR_REQUEST_PACKET)
                _request_counter += 1
            except Exception as e:
                print("[Serial] SENSOR_REQUEST write error:", e)

        time.sleep(1.0)


# -----------------------------
# 백그라운드: 계속 읽어서 마지막 패킷 보관
# -----------------------------
def _read_loop():
    global _last_raw_string, _last_reading, _last_read_time
    while _running:
        data = None
        with port_lock:
            if ser is None:
                break
            try:
                # 락 안에서 read 수행
                data = ser.read(1024)
            except Exception as e:
                print("[Serial] read error:", e)
                # 에러 발생 시 루프 잠시 중단
                time.sleep(0.2)
                continue

        if data:
            arr = _hex_list_from_bytes(data)
            raw_string = ",".join(arr)
            _last_raw_string = raw_string

            reading = _parse_sensor_packet(arr)
            if reading is not None:
                _last_reading = reading
                _last_read_time = time.time()

        time.sleep(0.02)


# -----------------------------
# GUI에서 주기적으로 호출하는 함수
# -----------------------------
def poll_sensor_once():
    """
    GUI 의 poll_serial() 에서 호출.

    return: (reading, raw_string, request_sent, age_sec)
      - reading: (temp, hum, co2, illum) 또는 None
      - raw_string: "02,02,ff,..." 형식 문자열
      - request_sent: 마지막 poll 이후 센서 요청을 최소 1번 보냈으면 True
      - age_sec: 마지막 유효 센서 데이터가 들어온 뒤 경과한 초 (없으면 None)
    """
    global _last_poll_seen_request_counter

    # 이 함수는 lock을 걸지 않음. 백그라운드 스레드에서 수집한 최신 값을 읽기만 함.
    if ser is None:
        return None, "시리얼 포트가 열려있지 않습니다.", False, None

    reading_copy = _last_reading
    raw_copy = _last_raw_string

    # 요청 카운터 비교해서 변화 있으면 True
    current = _request_counter
    if current != _last_poll_seen_request_counter:
        request_sent = True
        _last_poll_seen_request_counter = current
    else:
        request_sent = False

    if _last_read_time is None:
        age = None
    else:
        age = time.time() - _last_read_time

    return reading_copy, raw_copy, request_sent, age


# -----------------------------
# LED 제어 (전체 모드: Off / Mood / On)
# -----------------------------
def send_led_packet(mode: str):
    """
    mode: "Off" / "Mood" / "On"
    """
    packet = LED_PACKETS.get(mode)
    if packet is None:
        raise ValueError(f"Unknown LED mode: {mode}")

    with port_lock:
        if ser is None:
            raise RuntimeError("시리얼 포트가 열려있지 않습니다.")
        ser.write(packet)
        time.sleep(0.1) # 빠른 명령 전송 시 하드웨어 프리징 방지를 위한 딜레이


# -----------------------------
# 밝기 제어 (라인별) - 현재는 콘솔 로그만
# -----------------------------
def apply_brightness_levels(levels):
    """
    levels: 길이 7 리스트, 각 값은 0~100 (정수)

    ⚠ 중요:
      AnyGrow 문서에는 '라인별 밝기'에 대한 공식 패킷 스펙이 없음.
      그래서 여기서는 일단 보드에 직접 패킷을 보내지 않고
      '현재 시리얼이 열려 있는지 확인 + 값만 콘솔에 출력'만 한다.

      → 추후 LED control.exe 를 포트 스니핑해서 패킷을 알아내면
        이 함수 안에서 ser.write(actual_packet) 로 교체하면 된다.
    """
    with port_lock:
        if ser is None:
            print("[BRIGHT] 시리얼 포트가 열려있지 않습니다.")
            print("         (GUI에서 슬라이더는 움직이지만 실제 밝기는 아직 안 바뀝니다.)")
            return

        # 자리만 잡아 둔 부분: 나중에 실제 패킷 작성
        print("[BRIGHT] 7 라인 밝기 적용 요청:", levels)
        # 예시) 패킷 조합 후 ser.write(packet) 형태로 구현 예정
        time.sleep(0.1) # 빠른 명령 전송 시 하드웨어 프리징 방지를 위한 딜레이


# -----------------------------
# 양액 펌프 / UV 필터 제어
# -----------------------------
def send_pump(on: bool):
    """양액 펌프 ON/OFF (패킷 설정 전까지는 로그만 출력)"""
    packet = PUMP_ON_PACKET if on else PUMP_OFF_PACKET
    if packet is None:
        print("[PUMP] 패킷이 아직 설정되지 않았습니다.")
        print("       AnyGrow 프로토콜에서 양액펌프 ON/OFF 패킷 HEX를 찾아서")
        print("       PUMP_ON_PACKET / PUMP_OFF_PACKET 변수에 넣어주세요.")
        return

    with port_lock:
        if ser is None:
            print("[PUMP] 시리얼 포트가 열려있지 않습니다.")
            return
        try:
            ser.write(packet)
            print(f"[PUMP] {'ON' if on else 'OFF'} 패킷 전송")
            time.sleep(0.1) # 빠른 명령 전송 시 하드웨어 프리징 방지를 위한 딜레이
        except Exception as e:
            print("[PUMP] write error:", e)


def send_uv(on: bool):
    """UV 필터 ON/OFF (패킷 설정 전까지는 로그만 출력)"""
    packet = UV_ON_PACKET if on else UV_OFF_PACKET
    if packet is None:
        print("[UV] 패킷이 아직 설정되지 않았습니다.")
        print("       AnyGrow 프로토콜에서 UV FILTER ON/OFF 패킷 HEX를 찾아서")
        print("       UV_ON_PACKET / UV_OFF_PACKET 변수에 넣어주세요.")
        return

    with port_lock:
        if ser is None:
            print("[UV] 시리얼 포트가 열려있지 않습니다.")
            return
        try:
            ser.write(packet)
            print(f"[UV] {'ON' if on else 'OFF'} 패킷 전송")
            time.sleep(0.1) # 빠른 명령 전송 시 하드웨어 프리징 방지를 위한 딜레이
        except Exception as e:
            print("[UV] write error:", e)
