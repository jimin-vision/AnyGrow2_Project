import serial
import time

class AnyGrowDevice:
    def __init__(self, port="COM5"):
        """
        AnyGrow 장치와의 시리얼 통신을 초기화합니다.
        """
        try:
            self.ser = serial.Serial(
                port=port,
                baudrate=38400,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            print(f"{port}에 성공적으로 연결되었습니다.")
        except serial.SerialException as e:
            print(f"포트 {port}에 연결하는 중 오류 발생: {e}")
            self.ser = None

    def send_packet(self, packet_hex):
        """16진수 문자열로 된 패킷을 바이트로 변환하여 전송합니다."""
        if not self.ser or not self.ser.is_open:
            print("시리얼 포트가 열려있지 않습니다.")
            return
        
        packet_bytes = bytes.fromhex(packet_hex)
        print(f"전송: {packet_bytes.hex().upper()}")
        self.ser.write(packet_bytes)

    def set_brightness(self, level: int):
        """
        메인 LED의 밝기를 조절합니다. (가설)
        """
        if not 0 <= level <= 100:
            raise ValueError("밝기 레벨은 0에서 100 사이여야 합니다.")
        
        level_hex = f"{level:02x}"
        packet = f"0201FF4CFF00FF{level_hex}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        
        self.send_packet(packet)

    def set_pump_state(self, is_on: bool):
        """
        펌프를 켜거나 끕니다. (가설)
        """
        state_hex = "01" if is_on else "00"
        packet = f"0201FF4CFF01FF{state_hex}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        
        self.send_packet(packet)

    def set_uv_light_state(self, is_on: bool):
        """
        UV 라이트를 켜거나 끕니다. (가설)
        """
        state_hex = "01" if is_on else "00"
        packet = f"0201FF4CFF02FF{state_hex}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"

        self.send_packet(packet)

    def close(self):
        """시리얼 포트를 닫습니다."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("포트를 닫았습니다.")

if __name__ == "__main__":
    device = None
    try:
        device = AnyGrowDevice(port="COM5")
        if device.ser:
            print("="*30)
            print("테스트를 시작합니다. 5초 후에 시작되니 장치를 지켜봐주세요.")
            print("="*30)
            time.sleep(5)

            # --- 초기화: 모든 기능 끄기 ---
            print("\n[초기화] 모든 기능을 끕니다...")
            device.set_brightness(0)
            time.sleep(0.1)
            device.set_pump_state(False)
            time.sleep(0.1)
            device.set_uv_light_state(False)
            print("초기화 완료. 3초 후 테스트 시작.")
            time.sleep(3)

            # --- 테스트 1: 펌프 ---
            print("\n[테스트 1/3] 펌프를 5초간 켭니다...")
            device.set_pump_state(True)
            time.sleep(5)
            device.set_pump_state(False)
            print("펌프 테스트 완료.")
            time.sleep(2)

            # --- 테스트 2: UV 라이트 ---
            print("\n[테스트 2/3] UV 라이트를 3초간 켭니다...")
            device.set_uv_light_state(True)
            time.sleep(3)
            device.set_uv_light_state(False)
            print("UV 라이트 테스트 완료.")
            time.sleep(2)

            # --- 테스트 3: 밝기 조절 ---
            print("\n[테스트 3/3] 밝기를 50% -> 100% -> 0% 순으로 변경합니다...")
            print("밝기 50%...")
            device.set_brightness(50)
            time.sleep(3)
            print("밝기 100%...")
            device.set_brightness(100)
            time.sleep(3)
            print("밝기 0% (끄기)...")
            device.set_brightness(0)
            print("밝기 테스트 완료.")
            
            print("\n모든 테스트가 완료되었습니다.")
    except Exception as e:
        print(f"테스트 실행 중 오류가 발생했습니다: {e}")
    finally:
        if device:
            device.close()
