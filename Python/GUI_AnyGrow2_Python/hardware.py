# hardware.py
# AnyGrow2 hardware/protocol layer: serial, LED packets, sensor parsing

import serial
import time

# 기본 시리얼 설정 (필요하면 여기서 포트 수정)
SERIAL_PORT = "COM5"
BAUD_RATE = 38400

# LED 제어 패킷 (Node.js 코드와 동일)
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

# 센서 요청 패킷
SENSOR_REQUEST_PACKET = bytes.fromhex(
    "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
)

# 패킷 종료 표시 (JS에서 ETX='ff,ff')
ETX = "ff,ff"

# 내부 상태
ser = None
last_sensor_request_time = 0.0
_packet_buffer = ""


def init_serial(port=None, baudrate=None):
    """
    시리얼 포트를 연다. 이미 열려 있으면 그대로 사용.
    실패 시 예외를 던진다.
    """
    global ser
    if ser is not None and ser.is_open:
        return ser

    p = port or SERIAL_PORT
    b = baudrate or BAUD_RATE

    ser = serial.Serial(
        port=p,
        baudrate=b,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0,  # non-blocking
    )
    return ser


def close_serial():
    """시리얼 포트를 닫는다."""
    global ser
    if ser is not None and ser.is_open:
        ser.close()
    ser = None


def send_led_packet(mode):
    """
    LED 모드를 보낸다.
    mode: 'Off' / 'Mood' / 'On'
    실패 시 예외 발생.
    """
    global ser
    if ser is None or not ser.is_open:
        raise RuntimeError("Serial port is not open")

    packet = LED_PACKETS.get(mode)
    if packet is None:
        raise ValueError("Unknown LED mode: %r" % (mode,))

    ser.write(packet)
    # 최신 센서값도 같이 요청
    ser.write(SENSOR_REQUEST_PACKET)


def _hex2dec(arr, first, last):
    """
    anygrow2_client.js 의 hex2dec 함수 포팅:
    result = '';
    for(i=first;i<=last;i++){ result += String(eval(arr[i])-30); }
    return eval(result);
    """
    result = ""
    for i in range(first, last + 1):
        result += str(int(arr[i]) - 30)
    return int(result)


def _parse_sensor_packet(arr):
    """
    센서 패킷 파싱.
    arr 길이 30, arr[1]=='02' 인 경우
      온도, 습도, CO2, 조도 값을 반환.
    """
    if len(arr) != 30:
        return None
    if arr[1] != "02":
        return None

    try:
        temperature = _hex2dec(arr, 10, 12) / 10.0
        humidity = _hex2dec(arr, 14, 16) / 10.0
        co2 = _hex2dec(arr, 18, 21)
        illumination = _hex2dec(arr, 23, 26)
        return temperature, humidity, co2, illumination
    except Exception:
        return None


def poll_sensor_once():
    """
    센서 폴링을 한 번 수행한다. (non-blocking)
    반환값: (reading, raw_string, request_sent)

      reading: (temp, hum, co2, illum) 튜플 또는 None
      raw_string: 현재까지 누적된 패킷 문자열 (GUI 표시용)
      request_sent: 이 호출에서 센서 요청 패킷을 보냈으면 True
    """
    global ser, last_sensor_request_time, _packet_buffer

    reading = None
    raw_string = _packet_buffer
    request_sent = False

    if ser is None or not ser.is_open:
        return reading, raw_string, request_sent

    now = time.time()

    # 1초에 한 번 센서 요청
    if now - last_sensor_request_time >= 1.0:
        ser.write(SENSOR_REQUEST_PACKET)
        last_sensor_request_time = now
        request_sent = True

    # 데이터 읽기
    data = ser.read(1024)
    if data:
        hex_str = data.hex()
        part = ""
        for i, ch in enumerate(hex_str):
            if i != 0 and i % 2 == 0:
                part += ","
            part += ch

        _packet_buffer += part
        raw_string = _packet_buffer

        if ETX in _packet_buffer:
            arr = _packet_buffer.split(",")
            reading = _parse_sensor_packet(arr)
            _packet_buffer = ""
            raw_string = ""

    return reading, raw_string, request_sent
