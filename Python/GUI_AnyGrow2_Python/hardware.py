# hardware.py
# AnyGrow2 hardware/protocol layer: serial, LED packets, sensor parsing

import serial
import time

SERIAL_PORT = "COM5"
BAUD_RATE = 38400

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

ETX = "ff,ff"

ser = None
last_sensor_request_time = 0.0
_packet_buffer = ""


def init_serial(port=None, baudrate=None):
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
        timeout=0,
    )
    return ser


def close_serial():
    global ser
    if ser is not None and ser.is_open:
        ser.close()
    ser = None


def send_led_packet(mode):
    global ser
    if ser is None or not ser.is_open:
        raise RuntimeError("Serial port is not open")

    packet = LED_PACKETS.get(mode)
    if packet is None:
        raise ValueError("Unknown LED mode: %r" % (mode,))

    ser.write(packet)
    ser.write(SENSOR_REQUEST_PACKET)


def _hex2dec(arr, first, last):
    result = ""
    for i in range(first, last + 1):
        result += str(int(arr[i]) - 30)
    return int(result)


def _parse_sensor_packet(arr):
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
    한 번 폴링.
    return: (reading, raw_string, request_sent)
      reading: (t,h,c,il) or None
      raw_string: 누적 패킷 문자열
      request_sent: 이번 호출에서 센서 요청을 보냈는지 여부
    """
    global ser, last_sensor_request_time, _packet_buffer

    reading = None
    raw_string = _packet_buffer
    request_sent = False

    if ser is None or not ser.is_open:
        return reading, raw_string, request_sent

    now = time.time()

    if now - last_sensor_request_time >= 1.0:
        ser.write(SENSOR_REQUEST_PACKET)
        last_sensor_request_time = now
        request_sent = True

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
