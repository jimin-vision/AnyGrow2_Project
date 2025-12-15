# drivers/hardware.py
import serial
import time
import queue
from datetime import datetime
from PyQt5 import QtCore

# ============================================================
# Helper Functions & Packet Definitions
# ============================================================

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
        "humidity": h_raw / 10.0,
        "co2": c_raw,
        "illum": i_raw
    }

# Packet definitions remain the same
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
# Hardware Manager Class (QObject for threading)
# ============================================================

class HardwareManager(QtCore.QObject):
    
    # Signals to communicate with the GUI thread
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
        
        # Timers must be instance variables to be kept alive
        self.command_timer = None
        self.sensor_request_timer = None
        self.read_timer = None

    @QtCore.pyqtSlot()
    def reconnect(self):
        """Public slot to manually trigger a reconnection attempt."""
        self._ensure_serial_connection()

    @QtCore.pyqtSlot()
    def start(self):
        """Main worker loop for the hardware thread."""
        self._running = True
        
        # Timers for periodic tasks within this thread
        self.command_timer = QtCore.QTimer()
        self.command_timer.timeout.connect(self._process_command_queue)
        self.command_timer.start(100) # Process queue 10x per second

        self.sensor_request_timer = QtCore.QTimer()
        self.sensor_request_timer.timeout.connect(lambda: self.submit_command('sensor_req'))
        self.sensor_request_timer.start(1000) # Request sensor data every second

        # Initial connection attempt
        self._ensure_serial_connection()
        
    @QtCore.pyqtSlot()
    def stop(self):
        self.status_changed.emit("Stopping hardware thread...")
        self._running = False
        
        # Stop all timers
        if self.command_timer: self.command_timer.stop()
        if self.sensor_request_timer: self.sensor_request_timer.stop()
        if self.read_timer: self.read_timer.stop()

        if self._ser and self._ser.is_open:
            try:
                self._ser.close()
            except Exception as e:
                self.status_changed.emit(f"[ERROR] on close: {e}")
        self.status_changed.emit("Hardware thread stopped.")

    def _ensure_serial_connection(self):
        if self._ser and self._ser.is_open:
            return True
        
        # Stop any existing read timer before creating a new one
        if self.read_timer:
            self.read_timer.stop()

        try:
            self.status_changed.emit(f"Attempting to connect to {self.serial_port_name}...")
            self._ser = serial.Serial(
                port=self.serial_port_name,
                baudrate=self.baud_rate,
                timeout=0.1
            )
            self.status_changed.emit(f"Serial port {self.serial_port_name} connected.")
            
            # Start a timer to continuously read data
            self.read_timer = QtCore.QTimer()
            self.read_timer.timeout.connect(self._read_data)
            self.read_timer.start(50)
            return True
        except serial.SerialException as e:
            self.status_changed.emit(f"[ERROR] Failed to connect: {e}")
            self._ser = None
            # Retry connection after a delay
            QtCore.QTimer.singleShot(3000, self._ensure_serial_connection)
            return False

    def _read_data(self):
        if not self._running or not self._ser or not self._ser.is_open:
            return

        try:
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
            self.status_changed.emit(f"[ERROR] Serial read error: {e}")
            if self._ser:
                self._ser.close()
            self._ser = None
            # Trigger reconnection logic
            QtCore.QTimer.singleShot(1000, self._ensure_serial_connection)

    @QtCore.pyqtSlot(str, object)
    def submit_command(self, cmd: str, args=None):
        if not self._running:
            return
        self._command_queue.put((cmd, args))

    def _process_command_queue(self):
        if not self._ser or not self._ser.is_open:
            # Don't try to reconnect here, just wait. _ensure_serial_connection is handled by other parts.
            return

        try:
            cmd, args = self._command_queue.get_nowait()
        except queue.Empty:
            return # No command to process

        packet_to_send = None
        # Logic to build packet based on command
        if cmd == 'led' and args:
            packet_to_send = LED_PACKETS.get(args[0])
        elif cmd == 'pump' and args is not None:
            packet_to_send = PUMP_ON_PACKET if args[0] else PUMP_OFF_PACKET
        elif cmd == 'uv' and args is not None:
            packet_to_send = UV_ON_PACKET if args[0] else UV_OFF_PACKET
        elif cmd == 'sensor_req':
            packet_to_send = SENSOR_REQUEST_PACKET
            self.request_sent.emit()
        elif cmd == 'bms_time_sync' and args:
            hour_bcd = dec_to_bcd(args[0])
            minute_bcd = dec_to_bcd(args[1])
            second_bcd = dec_to_bcd(args[2])
            packet_str = f"0202FF54FF00FF{hour_bcd:02x}{minute_bcd:02x}{second_bcd:02x}FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF03"
            packet_to_send = bytes.fromhex(packet_str)
        # Add other command handling here...
        
        if packet_to_send:
            try:
                self._ser.write(packet_to_send)
            except Exception as e:
                self.status_changed.emit(f"[ERROR] Serial write error: {e}")
                if self._ser:
                    self._ser.close()
                self._ser = None
                # Re-queue the failed command
                self.submit_command(cmd, args)
                # Trigger reconnection logic by calling ensure_serial_connection
                QtCore.QTimer.singleShot(1000, self._ensure_serial_connection)
