# drivers/hardware.py
import time
import queue
from PyQt5 import QtCore

from core.protocol import PacketBuilder, PacketParser
from core.constants import COMMAND_INTERVAL
from drivers.serial_communicator import SerialCommunicator

def _hex_list_from_bytes(data: bytes):
    """바이트 문자열에서 16진수 문자열 리스트를 생성합니다."""
    hex_string = data.hex()
    return [hex_string[i:i+2] for i in range(0, len(hex_string), 2)]

class HardwareManager(QtCore.QObject):
    """
    하드웨어와의 통신을 오케스트레이션합니다.
    별도의 스레드에서 실행되며, 타이머, 명령어 큐, 재연결 로직을 관리하고,
    SerialCommunicator를 사용하여 실제 시리얼 I/O를 수행합니다.
    """
    status_changed = QtCore.pyqtSignal(str)
    data_updated = QtCore.pyqtSignal(dict)
    raw_string_updated = QtCore.pyqtSignal(str)
    request_sent = QtCore.pyqtSignal()

    def __init__(self, port="COM5", baud_rate=38400):
        super().__init__()
        self._communicator = SerialCommunicator(port, baud_rate)
        self._command_queue = queue.Queue()
        self._running = False
        self._mutex = QtCore.QMutex()
        self._last_write_timestamp = 0

        self.command_timer = None
        self.sensor_request_timer = None
        self.read_timer = None
        self.reconnect_timer = None
        
        self._command_map = {
            'sensor_req': lambda args: PacketBuilder.sensor_request(),
            'led': lambda args: PacketBuilder.led(args.get('mode')),
            'pump': lambda args: PacketBuilder.pump(args.get('on')),
            'uv': lambda args: PacketBuilder.uv(args.get('on')),
            'bms_time_sync': lambda args: PacketBuilder.bms_time_sync(args.get('hour', 0), args.get('minute', 0), args.get('second', 0)),
            'channel_led': lambda args: PacketBuilder.channel_led(args.get('settings', []))
        }

    @QtCore.pyqtSlot()
    def start(self):
        """하드웨어 관리자와 타이머를 시작합니다."""
        if self._running: return
        self._running = True
        self._setup_timers()
        self._connect()
        
    def _setup_timers(self):
        """하드웨어 관리자를 위한 타이머를 초기화하고 시작합니다."""
        self.command_timer = QtCore.QTimer()
        self.sensor_request_timer = QtCore.QTimer()
        self.read_timer = QtCore.QTimer()
        self.reconnect_timer = QtCore.QTimer()

        self.command_timer.timeout.connect(self._process_command_queue)
        self.sensor_request_timer.timeout.connect(lambda: self.submit_command('sensor_req'))
        self.read_timer.timeout.connect(self._read_data)
        self.reconnect_timer.timeout.connect(self._connect)
        self.reconnect_timer.setSingleShot(True)
        
        self.command_timer.start(50)
        self.sensor_request_timer.start(500)

    @QtCore.pyqtSlot()
    def stop(self):
        """하드웨어 관리자와 타이머를 중지합니다."""
        self.status_changed.emit("하드웨어 스레드 중지 중...")
        self._running = False
        
        if self.command_timer: self.command_timer.stop()
        if self.sensor_request_timer: self.sensor_request_timer.stop()
        if self.reconnect_timer: self.reconnect_timer.stop()
        
        self._disconnect()
        self.status_changed.emit("하드웨어 스레드 중지됨.")

    @QtCore.pyqtSlot()
    def reconnect(self):
        """수동으로 재연결을 시도합니다."""
        self.status_changed.emit("수동으로 재연결 요청...")
        print("[HARDWARE] 수동으로 재연결 요청...")
        
        if self.reconnect_timer and self.reconnect_timer.isActive():
            self.reconnect_timer.stop()
            
        self._disconnect()
        QtCore.QTimer.singleShot(100, self._connect)

    def _disconnect(self):
        """시리얼 포트 연결을 해제합니다."""
        self._mutex.lock()
        try:
            if self.read_timer: self.read_timer.stop()
            if self._communicator.is_open():
                self._communicator.disconnect()
                self.status_changed.emit("시리얼 포트 연결 해제됨.")
        finally:
            self._mutex.unlock()

    def _connect(self):
        """시리얼 포트에 연결합니다."""
        self._mutex.lock()
        try:
            if not self._running or self._communicator.is_open():
                return

            self.status_changed.emit(f"{self._communicator.port}에 연결 시도 중...")
            success, message = self._communicator.connect()
            self.status_changed.emit(message)
            
            if success:
                if self.read_timer: self.read_timer.start(50)
            elif self._running and self.reconnect_timer:
                self.reconnect_timer.start(3000)
        finally:
            self._mutex.unlock()

    def _handle_serial_error(self, error_msg):
        """시리얼 통신 오류를 처리합니다."""
        print(f"[HARDWARE] {error_msg}")
        self.status_changed.emit(error_msg)
        self._disconnect()
        
        if self._running and self.reconnect_timer and not self.reconnect_timer.isActive():
            self.reconnect_timer.start(1000)

    def _read_data(self):
        """시리얼 포트에서 데이터를 읽고 파싱합니다."""
        if not self._communicator.is_open(): return
        
        self._mutex.lock()
        try:
            data = self._communicator.read()
            if data:
                arr = _hex_list_from_bytes(data)
                self.raw_string_updated.emit(",".join(arr))
                reading = PacketParser.parse_sensor_packet(arr)
                if reading is not None:
                    reading['timestamp'] = time.time()
                    self.data_updated.emit(reading)
        except Exception as e:
            self._handle_serial_error(f"[오류] 시리얼 읽기 오류: {e}")
        finally:
            self._mutex.unlock()

    @QtCore.pyqtSlot(str, object)
    def submit_command(self, cmd: str, args=None):
        """명령 큐에 명령을 제출합니다."""
        if not self._running: return
        if args is None: args = {}
        self._command_queue.put((cmd, args))

    def _process_command_queue(self):
        """명령 큐를 처리하고 하드웨어에 명령을 보냅니다."""
        if time.time() - self._last_write_timestamp < COMMAND_INTERVAL:
            return
            
        if self._command_queue.empty():
            return

        try:
            cmd, args = self._command_queue.get_nowait()
        except queue.Empty:
            return

        builder = self._command_map.get(cmd)
        if not builder:
            self.status_changed.emit(f"[오류] 알 수 없는 명령: {cmd}")
            return
            
        packet_to_send = builder(args)
        if packet_to_send is None:
            self.status_changed.emit(f"[오류] 명령에 대한 패킷을 만들 수 없습니다: {cmd}")
            return

        self._write_to_serial(packet_to_send, cmd, args)

    def _write_to_serial(self, packet, cmd, args):
        """시리얼 포트에 패킷을 씁니다."""
        self._mutex.lock()
        try:
            if not self._communicator.is_open():
                self.submit_command(cmd, args) # Re-queue if disconnected
                return
            self._communicator.write(packet)
            print(f"[HARDWARE] 패킷 전송: {packet.hex().upper()}")
            self._last_write_timestamp = time.time()
            if cmd == 'sensor_req':
                self.request_sent.emit()
        except Exception as e:
            self._handle_serial_error(f"[오류] 시리얼 쓰기 오류: {e}")
        finally:
            self._mutex.unlock()