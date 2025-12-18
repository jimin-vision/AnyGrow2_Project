# drivers/serial_communicator.py
import serial
from serial.tools import list_ports

class SerialCommunicator:
    """
    pyserial 라이브러리를 감싸서 시리얼 포트와의 저수준 통신을 처리합니다.
    """
    def __init__(self, port="COM5", baud_rate=38400):
        self.port = port
        self.baud_rate = baud_rate
        self.ser = None

    def connect(self):
        """시리얼 포트에 연결합니다."""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=0.1,
                write_timeout=1.0
            )
            return True, f"시리얼 포트 {self.port} 연결됨."
        except serial.SerialException as e:
            available_ports = list_ports.comports()
            port_list_str = ", ".join([p.device for p in available_ports])
            if not port_list_str:
                port_list_str = "포트 없음"
            return False, f"[오류] 연결 실패: {e}. 사용 가능한 포트: [{port_list_str}]"

    def disconnect(self):
        """시리얼 포트 연결을 해제합니다."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            self.ser = None

    def is_open(self):
        """포트가 열려 있는지 확인합니다."""
        return self.ser and self.ser.is_open

    def read(self):
        """포트에서 데이터를 읽습니다."""
        if not self.is_open() or self.ser.in_waiting == 0:
            return None
        return self.ser.read(self.ser.in_waiting)

    def write(self, data: bytes):
        """포트에 데이터를 씁니다."""
        if not self.is_open():
            raise serial.SerialException("포트가 열려있지 않습니다.")
        self.ser.write(data)
