# core/protocol.py
import time
from datetime import datetime
from PyQt5.QtCore import QTime

# ============================================================
# Helper Functions & Constants
# ============================================================
def dec_to_bcd(n):
    """10진수를 BCD로 변환합니다."""
    return (n // 10) * 16 + (n % 10)

def _hex2dec(arr, first, last):
    """배열의 16진수 문자 범위를 10진수 숫자로 변환합니다."""
    result = ""
    for i in range(first, last + 1):
        try:
            v = int(arr[i], 16) - 0x30
            if not (0 <= v <= 9): return None
            result += str(v)
        except (ValueError, IndexError):
            return None
    return int(result) if result else None

# ============================================================
# Packet Parser Class
# ============================================================
class PacketParser:
    """수신된 데이터 패킷을 파싱하는 역할을 합니다."""
    @staticmethod
    def parse_sensor_packet(arr):
        """
        센서 데이터 패킷을 파싱합니다.
        16진수 문자열 리스트를 인자로 받습니다.
        """
        if len(arr) < 30: return None
        # 패킷 식별자 확인
        if arr[-30] != "02" or arr[-29] != "02": return None

        t_raw = _hex2dec(arr, -20, -18)
        h_raw = _hex2dec(arr, -16, -14)
        c_raw = _hex2dec(arr, -12, -9)
        i_raw = _hex2dec(arr, -7, -4)

        if None in (t_raw, h_raw, c_raw, i_raw): return None

        return {
            "temp": t_raw / 10.0,
            "hum": h_raw / 10.0,
            "co2": c_raw,
            "illum": i_raw
        }

# ============================================================
# Packet Builder Class
# ============================================================
class PacketBuilder:
    """
    하드웨어로 보낼 명령 패킷을 생성하는 역할을 합니다.
    각 메서드는 특정 명령에 대한 바이트 패킷을 반환합니다.
    """
    # 기본 패킷 구조
    _BASE_SENSOR_REQ = "0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    _BASE_LED_CMD = "0201FF4CFF00FF{mode}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    _BASE_PUMP_CMD = "0200FF59FF01FF{state}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    _BASE_UV_CMD = "0200FF59FF02FF{state}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    _BASE_TIME_SYNC_CMD = "0202FF54FF00FF{h}{m}{s}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
    _BASE_CH_LED_CMD = "0201FF4DFF00FF{payload}{padding}03"

    @staticmethod
    def sensor_request():
        """센서 데이터 요청 패킷을 생성합니다."""
        return bytes.fromhex(PacketBuilder._BASE_SENSOR_REQ)

    @staticmethod
    def led(mode: str):
        """LED 제어 패킷을 생성합니다."""
        mode_hex = {
            "Off": "00",
            "On": "01",
            "Mood": "02"
        }.get(mode, "00")
        return bytes.fromhex(PacketBuilder._BASE_LED_CMD.format(mode=mode_hex))

    @staticmethod
    def pump(on: bool):
        """펌프 제어 패킷을 생성합니다."""
        state_hex = "01" if on else "00"
        return bytes.fromhex(PacketBuilder._BASE_PUMP_CMD.format(state=state_hex))

    @staticmethod
    def uv(on: bool):
        """UV 필터 제어 패킷을 생성합니다."""
        state_hex = "01" if on else "00"
        return bytes.fromhex(PacketBuilder._BASE_UV_CMD.format(state=state_hex))

    @staticmethod
    def bms_time_sync(hour: int, minute: int, second: int):
        """BMS 시간 동기화 패킷을 생성합니다."""
        h_bcd = f"{dec_to_bcd(hour):02x}"
        m_bcd = f"{dec_to_bcd(minute):02x}"
        s_bcd = f"{dec_to_bcd(second):02x}"
        return bytes.fromhex(PacketBuilder._BASE_TIME_SYNC_CMD.format(h=h_bcd, m=m_bcd, s=s_bcd))

    @staticmethod
    def channel_led(settings: list):
        """채널별 LED 설정 패킷을 생성합니다."""
        if len(settings) != 4:
            return None
            
        payload = ""
        for setting in settings:
            on = 0x01 if setting.get('on') else 0x00
            hz = setting.get('hz', 1)
            brightness = setting.get('brightness', 0)
            hz_hi = (hz >> 8) & 0xFF
            hz_lo = hz & 0xFF
            payload += f"{on:02x}{hz_hi:02x}{hz_lo:02x}{brightness:02x}"
            
        padding_len = 30 - 7 - (len(payload) // 2) - 1
        if padding_len < 0: return None
        
        padding = 'FF' * padding_len
        
        packet_str = PacketBuilder._BASE_CH_LED_CMD.format(payload=payload, padding=padding)
        
        # 최종 길이 확인
        if len(packet_str) != 60: return None
        
        return bytes.fromhex(packet_str)
