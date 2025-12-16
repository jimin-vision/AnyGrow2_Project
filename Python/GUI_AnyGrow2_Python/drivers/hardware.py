# drivers/hardware.py
import serial
import time
import queue
import gc
from datetime import datetime
from PyQt5 import QtCore

# ============================================================
# Helper Functions & Constants
# ============================================================
COMMAND_INTERVAL = 0.2 # 200ms between commands to prevent spamming

def dec_to_bcd(n):
    return (n // 10) * 16 + (n % 10)

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

    return {
        "temp": t_raw / 10.0,
        "hum": h_raw / 10.0,
        "co2": c_raw,
        "illum": i_raw
    }

# Packet definitions
SENSOR_REQUEST_PACKET = bytes.fromhex("0202FF53FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03")
LED_PACKETS = {
    "Off": bytes.fromhex("0201FF4CFF00FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"),
    "Mood": bytes.fromhex("0201FF4CFF00FF02FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"),
    "On": bytes.fromhex("0201FF4CFF00FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"),
}
PUMP_ON_PACKET = bytes.fromhex("0200FF59FF01FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03")
PUMP_OFF_PACKET = bytes.fromhex("0200FF59FF01FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03")
UV_ON_PACKET = bytes.fromhex("0200FF59FF02FF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03")
UV_OFF_PACKET = bytes.fromhex("0200FF59FF02FF00FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03")

# ============================================================
# Hardware Manager Class
# ============================================================

class HardwareManager(QtCore.QObject):
    
    status_changed = QtCore.pyqtSignal(str)
    data_updated = QtCore.pyqtSignal(dict)
    raw_string_updated = QtCore.pyqtSignal(str)
    request_sent = QtCore.pyqtSignal()

    def __init__(self, port="COM5", baud_rate=38400):
        super().__init__()
        self.serial_port_name = port
        self.baud_rate = baud_rate
        
        self._ser = None
        self._command_queue = queue.Queue()
        self._running = False
        self._mutex = QtCore.QMutex()
        self._is_connected = False
        self._last_write_timestamp = 0

        self.command_timer = None
        self.sensor_request_timer = None
        self.read_timer = None
        self.reconnect_timer = None

    @QtCore.pyqtSlot()
    def start(self):
        if self._running: return
        self._running = True
        
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

        self._connect()
        
    @QtCore.pyqtSlot()
    def stop(self):
        self.status_changed.emit("Stopping hardware thread...")
        self._running = False
        
        if self.command_timer: self.command_timer.stop()
        if self.sensor_request_timer: self.sensor_request_timer.stop()
        if self.reconnect_timer: self.reconnect_timer.stop()
        
        self._disconnect()
        self.status_changed.emit("Hardware thread stopped.")

    @QtCore.pyqtSlot()
    def reconnect(self):
        self.status_changed.emit("Manual reconnect requested...")
        print("[HARDWARE] Manual reconnect requested...")
        
        if self.reconnect_timer and self.reconnect_timer.isActive():
            self.reconnect_timer.stop()
            
        self._disconnect()
        QtCore.QTimer.singleShot(100, self._connect)

    def _disconnect(self):
        self._mutex.lock()
        try:
            if self.read_timer: self.read_timer.stop()
            if self._ser:
                if self._ser.is_open:
                    self._ser.close()
                del self._ser
                self._ser = None
                gc.collect()
                if self._is_connected:
                    msg = "Serial port disconnected."
                    self.status_changed.emit(msg)
                    print(f"[HARDWARE] {msg}")
            self._is_connected = False
        except Exception as e:
            msg = f"[ERROR] on disconnect: {e}"
            self.status_changed.emit(msg)
            print(f"[HARDWARE] {msg}")
        finally:
            self._mutex.unlock()

    def _connect(self):
        self._mutex.lock()
        try:
            if not self._running or self._is_connected:
                return

            msg = f"Attempting to connect to {self.serial_port_name}..."
            self.status_changed.emit(msg)
            print(f"[HARDWARE] {msg}")
            
            self._ser = serial.Serial(
                port=self.serial_port_name,
                baudrate=self.baud_rate,
                timeout=0.1,
                write_timeout=1.0
            )
            self._is_connected = True
            
            msg = f"Serial port {self.serial_port_name} connected."
            self.status_changed.emit(msg)
            print(f"[HARDWARE] {msg}")
            
            if self.read_timer: self.read_timer.start(50)

        except serial.SerialException as e:
            self._is_connected = False
            msg = f"[ERROR] Failed to connect: {e}"
            self.status_changed.emit(msg)
            print(f"[HARDWARE] {msg}")
            if self._running and self.reconnect_timer:
                self.reconnect_timer.start(3000)
        finally:
            self._mutex.unlock()

    def _handle_serial_error(self, error_msg):
        print(f"[HARDWARE] {error_msg}")
        self.status_changed.emit(error_msg)
        self._disconnect()
        
        if self._running and self.reconnect_timer and not self.reconnect_timer.isActive():
            self.reconnect_timer.start(1000)

    def _read_data(self):
        if not self._is_connected: return
        
        self._mutex.lock()
        try:
            if not self._ser or not self._ser.is_open: return

            if self._ser.in_waiting > 0:
                data = self._ser.read(self._ser.in_waiting)
                if data:
                    arr = _hex_list_from_bytes(data)
                    raw_string = ",".join(arr)
                    self.raw_string_updated.emit(raw_string)
                    reading = _parse_sensor_packet(arr)
                    if reading is not None:
                        reading['timestamp'] = time.time()
                        self.data_updated.emit(reading)
        except Exception as e:
            self._handle_serial_error(f"[ERROR] Serial read error: {e}")
        finally:
            self._mutex.unlock()

    @QtCore.pyqtSlot(str, object)
    def submit_command(self, cmd: str, args=None):
        if not self._running: return
        if args is None: args = {}
        self._command_queue.put((cmd, args))

    def _process_command_queue(self):
        now = time.time()
        if now - self._last_write_timestamp < COMMAND_INTERVAL:
            return
            
        if self._command_queue.empty():
            return

        try:
            cmd, args = self._command_queue.get_nowait()
        except queue.Empty:
            return

        packet_to_send = None
        if cmd == 'sensor_req':
            packet_to_send = SENSOR_REQUEST_PACKET
        elif cmd == 'led' and args:
            packet_to_send = LED_PACKETS.get(args.get('mode'))
        elif cmd == 'pump' and 'on' in args:
            packet_to_send = PUMP_ON_PACKET if args.get('on') else PUMP_OFF_PACKET
        elif cmd == 'uv' and 'on' in args:
            packet_to_send = UV_ON_PACKET if args.get('on') else UV_OFF_PACKET
        elif cmd == 'bms_time_sync' and args:
            hour_bcd = dec_to_bcd(args.get('hour', 0))
            minute_bcd = dec_to_bcd(args.get('minute', 0))
            second_bcd = dec_to_bcd(args.get('second', 0))
            packet_str = f"0202FF54FF00FF{hour_bcd:02x}{minute_bcd:02x}{second_bcd:02x}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
            packet_to_send = bytes.fromhex(packet_str)
        elif cmd == 'channel_led' and 'settings' in args:
            settings = args.get('settings', [])
            if len(settings) == 4:
                payload = ""
                for setting in settings:
                    on = 0x01 if setting.get('on') else 0x00
                    hz = setting.get('hz', 1)
                    brightness = setting.get('brightness', 0)
                    hz_hi = (hz >> 8) & 0xFF
                    hz_lo = hz & 0xFF
                    payload += f"{on:02x}{hz_hi:02x}{hz_lo:02x}{brightness:02x}"
                padding_len = 30 - 7 - (len(payload)//2) - 1
                packet_str = f"0201FF4DFF00FF{payload}{'FF'*padding_len}03"
                if len(packet_str) == 60:
                    packet_to_send = bytes.fromhex(packet_str)
                else:
                    self.status_changed.emit("[ERROR] Channel LED packet length is incorrect.")

        if packet_to_send:
            self._mutex.lock()
            try:
                if not self._is_connected or not self._ser or not self._ser.is_open:
                    # If disconnected between check and write, re-queue and let next cycle handle it.
                    self.submit_command(cmd, args)
                    return
                self._ser.write(packet_to_send)
                self._last_write_timestamp = time.time()
                if cmd == 'sensor_req':
                    self.request_sent.emit()
            except Exception as e:
                self._handle_serial_error(f"[ERROR] Serial write error: {e}")
            finally:
                self._mutex.unlock()