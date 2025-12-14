# hardware.py
# Refactored for stability with a command queue architecture.
# AnyGrow2 보드와 시리얼 통신 + 센서 데이터 파싱 + LED/펌프/UV + (자리만 잡아 둔) 밝기 제어

import serial
import time
import threading
import queue

# -----------------------------
# 시리얼 설정
# -----------------------------
SERIAL_PORT = "COM5"   # 필요하면 여기만 수정
BAUD_RATE = 38400

ser = None
port_lock = threading.Lock()
command_queue = queue.Queue()

# -----------------------------
# 패킷 정의
# -----------------------------
SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)

LED_PACKETS = {
    "Off": bytes.fromhex("0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"),
    "Mood": bytes.fromhex("0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"),
    "On": bytes.fromhex("0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"),
}

PUMP_ON_PACKET = None
PUMP_OFF_PACKET = None
UV_ON_PACKET = None
UV_OFF_PACKET = None

# -----------------------------
# 내부 상태
# -----------------------------
_last_raw_string = "(아직 수신된 데이터 없음)"
_last_reading = None
_last_read_time = None
_request_counter = 0
_last_poll_seen_request_counter = 0
_running = False

# -----------------------------
# 헬퍼: 센서 데이터 파싱
# -----------------------------
def _hex_list_from_bytes(data: bytes):
    hex_string = data.hex()
    return [hex_string[i:i+2] for i in range(0, len(hex_string), 2)]

def _hex2dec(arr, first, last):
    result = ""
    for i in range(first, last + 1):
        v = int(arr[i], 16) - 0x30
        if not (0 <= v <= 9): return None
        result += str(v)
    return int(result) if result else None

def _parse_sensor_packet(arr):
    if len(arr) < 30: return None
    arr = arr[-30:]
    if arr[1] != "02": return None
    
    t_raw = _hex2dec(arr, 10, 12)
    h_raw = _hex2dec(arr, 14, 16)
    c_raw = _hex2dec(arr, 18, 21)
    i_raw = _hex2dec(arr, 23, 26)

    if None in (t_raw, h_raw, c_raw, i_raw): return None

    return (t_raw / 10.0, h_raw / 10.0, c_raw, i_raw)

# -----------------------------
# Public API: 초기화, 종료, 명령 제출
# -----------------------------
def init_serial():
    global ser, _running, _request_counter
    try:
        # Port lock is acquired here for the initial open
        with port_lock:
            ser = serial.Serial(
                port=SERIAL_PORT,
                baudrate=BAUD_RATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1,
            )
        
        _running = True
        _request_counter = 0
        
        # 모든 백그라운드 스레드 시작
        threading.Thread(target=_read_loop, daemon=True).start()
        threading.Thread(target=_command_worker_loop, daemon=True).start()
        threading.Thread(target=_sensor_request_loop, daemon=True).start()

    except serial.SerialException as e:
        print(f"[ERROR] 시리얼 포트를 열 수 없습니다: {e}")
        ser = None
        _running = False # 스레드가 시작되지 않도록 확실히 함
        return

def close_serial():
    global _running
    _running = False
    # 작업자 스레드가 루프를 종료하도록 명령
    if command_queue:
        command_queue.put(('exit', []))

    # 잠시 기다린 후 포트 닫기
    time.sleep(0.2)
    with port_lock:
        global ser
        if ser is not None:
            try:
                ser.close()
            except Exception:
                pass
            ser = None

def submit_command(cmd: str, *args):
    """UI가 하드웨어에 명령을 보낼 때 사용하는 유일한 함수."""
    if not _running or ser is None:
        print(f"[WARN] 시리얼이 연결되지 않아 '{cmd}' 명령을 무시합니다.")
        return
    command_queue.put((cmd, args))

def _create_channel_led_packet(settings: list) -> bytes:
    """
    채널별 LED 설정을 위한 시리얼 패킷을 생성합니다.
    settings: [{'on': bool, 'hz': int, 'brightness': int}]
    
    TODO: 실제 하드웨어 프로토콜에 맞게 패킷 형식을 구현해야 합니다.
    """
    print(f"[TODO] 실제 패킷 생성 로직 필요. 설정: {settings}")
    # 예시: return bytes.fromhex("...")
    return None

# -----------------------------
# 백그라운드 스레드 루프
# -----------------------------
def _read_loop():
    """백그라운드에서 계속 시리얼 포트를 읽고 마지막 유효한 센서 값을 파싱하여 저장."""
    global _last_raw_string, _last_reading, _last_read_time
    while _running:
        data = None
        try:
            # 모든 시리얼 접근은 port_lock으로 보호
            with port_lock:
                if ser and ser.is_open and ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
        except Exception as e:
            print(f"[Serial] Read error: {e}")
            time.sleep(0.5) # 에러 발생 시 잠시 대기
            continue
        
        if data:
            arr = _hex_list_from_bytes(data)
            raw_string = ",".join(arr)
            _last_raw_string = raw_string
            
            reading = _parse_sensor_packet(arr)
            if reading is not None:
                _last_reading = reading
                _last_read_time = time.time()
        
        time.sleep(0.05) # CPU 사용량 줄이기

def _sensor_request_loop():
    """1초마다 센서 데이터 요청 명령을 큐에 추가."""
    while _running:
        submit_command('sensor_req')
        time.sleep(1.0)

def _command_worker_loop():
    """
    모든 쓰기 작업을 처리하는 유일한 스레드.
    큐에서 명령을 하나씩 꺼내 순차적으로 실행하여 명령어 충돌을 방지.
    """
    global _request_counter
    while _running:
        try:
            cmd, args = command_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        if cmd == 'exit':
            break

        packet_to_send = None
        
        with port_lock:
            if ser is None or not ser.is_open:
                continue

            try:
                if cmd == 'led':
                    mode = args[0]
                    packet_to_send = LED_PACKETS.get(mode)
                    if packet_to_send:
                        print(f"[CMD] LED 명령 전송: {mode}")

                elif cmd == 'pump':
                    on = args[0]
                    packet_to_send = PUMP_ON_PACKET if on else PUMP_OFF_PACKET
                    if packet_to_send:
                         print(f"[CMD] 양액 펌프: {'On' if on else 'Off'} 명령 전송")
                    else:
                        print("[PUMP] 패킷이 아직 설정되지 않았습니다.")

                elif cmd == 'uv':
                    on = args[0]
                    packet_to_send = UV_ON_PACKET if on else UV_OFF_PACKET
                    if packet_to_send:
                        print(f"[CMD] UV 필터: {'On' if on else 'Off'} 명령 전송")
                    else:
                        print("[UV] 패킷이 아직 설정되지 않았습니다.")
                
                elif cmd == 'brightness':
                    levels = args[0]
                    print(f"[CMD] 7 라인 밝기 적용 요청: {levels}")
                    # 실제 패킷 전송 로직이 확정되면 여기에 추가
                    # packet_to_send = ...

                elif cmd == 'channel_led':
                    settings = args[0]
                    print(f"[CMD] 채널별 LED 설정 적용 요청: {settings}")
                    packet_to_send = _create_channel_led_packet(settings)

                elif cmd == 'sensor_req':
                    packet_to_send = SENSOR_REQUEST_PACKET
                    _request_counter += 1

                if packet_to_send:
                    ser.write(packet_to_send)

            except Exception as e:
                print(f"[ERROR] 명령 '{cmd}' 실행 중 오류 발생: {e}")
        
        # 락을 해제한 후, 다음 명령 처리 전에 짧은 딜레이를 줌
        time.sleep(0.1)

# -----------------------------
# GUI에서 주기적으로 호출하는 함수
# -----------------------------
def poll_sensor_once():
    """
    GUI의 poll_serial()에서 호출.
    백그라운드 스레드가 수집한 최신 값을 읽기만 함 (시리얼 직접 접근 X).
    """
    global _last_poll_seen_request_counter
    if not _running:
        return None, "시리얼 포트가 닫혀있습니다.", False, None

    reading_copy = _last_reading
    raw_copy = _last_raw_string

    current = _request_counter
    request_sent = current != _last_poll_seen_request_counter
    if request_sent:
        _last_poll_seen_request_counter = current

    age = time.time() - _last_read_time if _last_read_time else None
    
    return reading_copy, raw_copy, request_sent, age