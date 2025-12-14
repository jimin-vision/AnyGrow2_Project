import serial
import time

class AnyGrowDeviceFinal:
    def __init__(self, port="COM5"):
        try:
            self.ser = serial.Serial(port=port, baudrate=38400, timeout=1)
            print(f"{port}에 성공적으로 연결되었습니다.")
        except serial.SerialException as e:
            print(f"포트 {port}에 연결하는 중 오류 발생: {e}")
            self.ser = None

    def send_packet(self, packet_hex):
        if not self.ser or not self.ser.is_open:
            print("시리얼 포트가 열려있지 않습니다.")
            return
        packet_bytes = bytes.fromhex(packet_hex)
        print(f"전송: {packet_bytes.hex().upper()}")
        self.ser.write(packet_bytes)

    def _send_device_command(self, cmd_char: str, state_on: bool):
        """
        특정 CMD 문자를 사용하여 장치를 제어합니다.
        :param cmd_char: 'P' (Pump), 'U' (UV Light) 등
        :param state_on: True는 On (0x01), False는 Off (0x00)
        """
        cmd_hex = f"{ord(cmd_char):02x}"  # 'P' -> 50, 'U' -> 55
        state_hex = "01" if state_on else "00"
        # STX | MODE | NULL | CMD | NULL | CH | NULL | STATE | NULL... 
        packet = f"0201FF{cmd_hex}FF00FF{state_hex}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        self.send_packet(packet)

    def set_pump_state(self, is_on: bool):
        self._send_device_command('P', is_on)

    def set_uv_light_state(self, is_on: bool):
        self._send_device_command('U', is_on)

    def set_led_off(self):
        """모든 LED 기능을 끕니다."""
        packet = "0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
        self.send_packet(packet)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("포트를 닫았습니다.")

if __name__ == "__main__":
    device = None
    try:
        device = AnyGrowDeviceFinal(port="COM5")
        if device.ser:
            print("="*30)
            print("마지막 테스트를 시작합니다. 5초 후에 시작됩니다.")
            print("="*30)
            time.sleep(5)

            # --- 초기화 ---
            print("\n[초기화] 모든 기능을 끕니다...")
            device.set_led_off()
            time.sleep(0.2)
            device.set_pump_state(False)
            time.sleep(0.2)
            device.set_uv_light_state(False)
            print("초기화 완료. 3초 후 테스트 시작.")
            time.sleep(3)

            # --- 테스트 1: 펌프 ('P' 명령어) ---
            print("\n[테스트 1/2] 펌프를 5초간 켭니다... (CMD='P')")
            device.set_pump_state(True)
            time.sleep(5)
            device.set_pump_state(False)
            print("펌프 테스트 완료.")
            time.sleep(2)

            # --- 테스트 2: UV 라이트 ('U' 명령어) ---
            print("\n[테스트 2/2] UV 라이트를 5초간 켭니다... (CMD='U')")
            device.set_uv_light_state(True)
            time.sleep(5)
            device.set_uv_light_state(False)
            print("UV 라이트 테스트 완료.")
            
            print("\n\n모든 테스트가 완료되었습니다.")
    except Exception as e:
        print(f"테스트 실행 중 오류가 발생했습니다: {e}")
    finally:
        if device:
            device.close()
