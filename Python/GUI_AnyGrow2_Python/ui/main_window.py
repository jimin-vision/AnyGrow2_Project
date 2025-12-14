# ui/main_window.py
# AnyGrow2 PyQt GUI (Refactored)

import sys
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from drivers import hardware as hw

from ui.widgets.sensor_widget import SensorWidget
from ui.widgets.raw_data_widget import RawDataWidget
from ui.widgets.control_widget import ControlWidget

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AnyGrow2 PyQt GUI")
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self._last_valid_co2 = None
        self._last_console_print_time = 0.0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(10, 2, 10, 2)
        root_layout.setSpacing(8)

        # =============================
        # Setup UI Panels
        # =============================
        self._setup_top_bar(root_layout)
        
        main_row = QtWidgets.QHBoxLayout()
        root_layout.addLayout(main_row, 1)

        # Left panel
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(8)
        self.sensor_widget = SensorWidget()
        self.raw_data_widget = RawDataWidget()
        self._setup_timer_controls() # Create timer controls
        
        left_panel.addWidget(self.sensor_widget, 0)
        left_panel.addWidget(self.raw_data_widget, 0)
        left_panel.addWidget(self.gb_timer) # Add timer groupbox to left panel
        left_panel.addStretch(1)
        main_row.addLayout(left_panel, 1)

        # Right panel (with scroll)
        self.control_widget = ControlWidget()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.control_widget)
        main_row.addWidget(scroll_area, 0)

        # Calculate optimal size and increase
        optimal_size = self.sizeHint()
        self.resize(int(optimal_size.width() * 1.05), int(optimal_size.height() * 1.2)) # Width multiplier changed to 1.05

        # =============================
        # Connect Signals
        # =============================
        self.control_widget.led_command.connect(self.send_led_command)
        self.control_widget.channel_led_command.connect(self.apply_channel_led_from_gui)
        self.control_widget.pump_command.connect(self.send_pump_command)
        self.control_widget.uv_command.connect(self.send_uv_command)
        self.control_widget.bms_time_sync_command.connect(self.sync_bms_time)

        # =============================
        # Timers
        # =============================
        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.setInterval(200)
        self.poll_timer.timeout.connect(self.poll_serial)

    def _setup_top_bar(self, root_layout):
        top_bar = QtWidgets.QHBoxLayout()
        root_layout.addLayout(top_bar)

        lbl_serial_title = QtWidgets.QLabel("시리얼 상태:")
        lbl_serial_title.setStyleSheet("font-weight: bold;")
        self.lbl_serial_status = QtWidgets.QLabel("프로그램 시작")

        top_bar.addWidget(lbl_serial_title)
        top_bar.addWidget(self.lbl_serial_status)
        top_bar.addStretch(1)

        self.btn_reconnect = QtWidgets.QPushButton("시리얼 재연결")
        self.btn_reconnect.clicked.connect(self.reconnect_serial)
        top_bar.addWidget(self.btn_reconnect)

        lbl_req_title = QtWidgets.QLabel("센서 요청 횟수:")
        self.lbl_req_count = QtWidgets.QLabel("0")

        top_bar.addWidget(lbl_req_title)
        top_bar.addWidget(self.lbl_req_count)
        
    def _setup_timer_controls(self):
        self.gb_timer = QtWidgets.QGroupBox("타이머 제어")
        timer_grid = QtWidgets.QGridLayout(self.gb_timer)
        
        # Start Time
        timer_grid.addWidget(QtWidgets.QLabel("시작 시간:"), 0, 0)
        self.spin_start_hour = QtWidgets.QSpinBox()
        self.spin_start_hour.setRange(0, 23)
        self.spin_start_hour.setSuffix("시")
        self.spin_start_hour.setValue(QtCore.QTime.currentTime().hour()) # Default to current hour
        timer_grid.addWidget(self.spin_start_hour, 0, 1)
        self.spin_start_min = QtWidgets.QSpinBox()
        self.spin_start_min.setRange(0, 59)
        self.spin_start_min.setSuffix("분")
        self.spin_start_min.setValue(QtCore.QTime.currentTime().minute()) # Default to current minute
        timer_grid.addWidget(self.spin_start_min, 0, 2)
        btn_set_start_now = QtWidgets.QPushButton("현재시간")
        btn_set_start_now.clicked.connect(self._set_start_time_now)
        timer_grid.addWidget(btn_set_start_now, 0, 3)

        # End time
        timer_grid.addWidget(QtWidgets.QLabel("종료 시간:"), 1, 0)
        self.spin_end_hour = QtWidgets.QSpinBox()
        self.spin_end_hour.setRange(0, 23)
        self.spin_end_hour.setSuffix("시")
        self.spin_end_hour.setValue(QtCore.QTime.currentTime().hour()) # Default to current hour
        timer_grid.addWidget(self.spin_end_hour, 1, 1)
        self.spin_end_min = QtWidgets.QSpinBox()
        self.spin_end_min.setRange(0, 59)
        self.spin_end_min.setSuffix("분")
        self.spin_end_min.setValue(QtCore.QTime.currentTime().minute()) # Default to current minute
        timer_grid.addWidget(self.spin_end_min, 1, 2)
        btn_set_end_now = QtWidgets.QPushButton("현재시간")
        btn_set_end_now.clicked.connect(self._set_end_time_now)
        timer_grid.addWidget(btn_set_end_now, 1, 3)
        
        # Target device
        timer_grid.addWidget(QtWidgets.QLabel("제어 대상:"), 2, 0)
        self.cmb_timer_target = QtWidgets.QComboBox()
        self.cmb_timer_target.addItems(["전체 LED", "양액 펌프", "UV 필터"])
        timer_grid.addWidget(self.cmb_timer_target, 2, 1, 1, 3) # Span 3 columns now

        # Start button
        btn_start_timer = QtWidgets.QPushButton("타이머 시작")
        btn_start_timer.clicked.connect(self.handle_timer_command)
        timer_grid.addWidget(btn_start_timer, 3, 0, 1, 4) # Span 4 columns now

    # ============================================================
    # UI Helpers
    # ============================================================
    def _show_error(self, title: str, msg: str):
        QtWidgets.QMessageBox.critical(self, title, msg)

    def set_serial_status(self, text: str):
        self.lbl_serial_status.setText(text)

    def set_request_count(self, n: int):
        self.lbl_req_count.setText(str(n))
        
    def _set_start_time_now(self):
        current_time = QtCore.QTime.currentTime()
        self.spin_start_hour.setValue(current_time.hour())
        self.spin_start_min.setValue(current_time.minute())

    def _set_end_time_now(self):
        current_time = QtCore.QTime.currentTime()
        self.spin_end_hour.setValue(current_time.hour())
        self.spin_end_min.setValue(current_time.minute())

    # ============================================================
    # Hardware Control Slots
    # ============================================================
    def send_led_command(self, mode: str):
        self.set_serial_status(f"LED 명령 예약: {mode}")
        hw.submit_command('led', mode)

    def send_pump_command(self, on: bool):
        status = 'On' if on else 'Off'
        self.set_serial_status(f"양액 펌프 명령 예약: {status}")
        hw.submit_command('pump', on)

    def send_uv_command(self, on: bool):
        status = 'On' if on else 'Off'
        self.set_serial_status(f"UV 필터 명령 예약: {status}")
        hw.submit_command('uv', on)

    def apply_channel_led_from_gui(self, settings: list):
        self.set_serial_status(f"채널별 LED 설정 명령 예약: {settings}")
        hw.submit_command('channel_led', settings)

    def sync_bms_time(self):
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        self.set_serial_status(f"BMS 시간 동기화 명령 예약: {hour:02d}:{minute:02d}")
        hw.submit_command('bms_time_sync', (hour, minute))

    def handle_timer_command(self):
        target = self.cmb_timer_target.currentText()
        
        start_hour = self.spin_start_hour.value()
        start_min = self.spin_start_min.value()
        start_time = QtCore.QTime(start_hour, start_min)

        end_hour = self.spin_end_hour.value()
        end_min = self.spin_end_min.value()
        end_time = QtCore.QTime(end_hour, end_min)
        
        current_time = QtCore.QTime.currentTime()
        # For a simple 'turn off at end_time' timer, we use msecsTo(end_time)
        msecs_until_end = current_time.msecsTo(end_time)

        # If start_time is in the future, we would need to schedule a separate 'turn on' event.
        # For now, focusing on the 'turn off' at end_time.
        # If the user wants an 'on duration' from start to end, that would be more complex.
        
        if msecs_until_end < 0:
            self.set_serial_status(f"[경고] 타이머 종료 시간이 이미 지났습니다.")
            return

        off_function = None
        if target == "전체 LED":
            off_function = lambda: self.send_led_command("Off")
        elif target == "양액 펌프":
            off_function = lambda: self.send_pump_command(False)
        elif target == "UV 필터":
            off_function = lambda: self.send_uv_command(False)

        if off_function:
            QtCore.QTimer.singleShot(msecs_until_end, off_function)
            self.set_serial_status(f"[{target}] 타이머 설정 완료. {end_time.toString('HH:mm')}에 꺼집니다.")
        else:
            self.set_serial_status(f"[에러] 알 수 없는 타이머 대상입니다: {target}")

    # ============================================================
    # Sensor Polling / Reconnect
    # ============================================================
    def poll_serial(self):
        try:
            reading, raw_string, request_sent, age_sec = hw.poll_sensor_once()
        except Exception as e:
            self.set_serial_status(f"[ERROR] 센서 폴링 실패: {e}")
            return

        self.raw_data_widget.set_text(raw_string)

        if request_sent:
            try:
                cnt = int(self.lbl_req_count.text()) + 1
            except ValueError:
                cnt = 1
            self.set_request_count(cnt)

        if age_sec is None:
            self.sensor_widget.set_sensor_status_text("센서 데이터 수신 기록 없음")
        else:
            if age_sec < 5.0:
                self.sensor_widget.set_sensor_status_text(f"센서 통신 정상 (마지막 수신 {age_sec:4.1f}초 전)")
            else:
                self.sensor_widget.set_sensor_status_text(f"⚠ 센서 데이터 안 들어옴 (마지막 수신 {age_sec:4.1f}초 전)")

        if reading is None:
            return

        t, h, c, il = reading

        if c is not None and c >= 6000:
            c = self._last_valid_co2 if self._last_valid_co2 is not None else 0
        else:
            self._last_valid_co2 = c

        self.sensor_widget.update_sensor_bars(t, h, int(c), int(il))
        self.sensor_widget.set_last_update_text(datetime.now().strftime("마지막 갱신: %Y-%m-%d %H:%M:%S"))

        now = time.time()
        if now - self._last_console_print_time >= 1.0:
            print(f"[SENSOR] T={t:.1f}C, H={h:.1f}%, CO2={c}ppm, Illum={il}lx")
            self._last_console_print_time = now

    def reconnect_serial(self):
        self.btn_reconnect.setEnabled(False)
        self.set_serial_status("시리얼 재연결 시도 중...")

        try:
            hw.close_serial()
        except Exception:
            pass

        self.set_request_count(0)
        self.sensor_widget.reset()
        self.raw_data_widget.reset()
        self._last_console_print_time = 0.0
        self._last_valid_co2 = None

        QtCore.QTimer.singleShot(300, self._do_reconnect)

    def _do_reconnect(self):
        try:
            hw.init_serial()
            self.set_serial_status(f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 재연결 완료")
        except Exception as e:
            self.set_serial_status(f"[ERROR] 시리얼 재연결 실패: {e}")
            self._show_error("Serial Reconnect Error", str(e))
        finally:
            self.btn_reconnect.setEnabled(True)

    # ============================================================
    # Execution
    # ============================================================
    def start_timers(self):
        if not self.poll_timer.isActive():
            self.poll_timer.start()

    def try_init_serial(self):
        try:
            hw.init_serial()
            self.set_serial_status(f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 연결됨")
        except Exception as e:
            self.set_serial_status(f"[ERROR] 시리얼 오픈 실패: {e}")
            self._show_error("Serial Error", str(e))

    def closeEvent(self, event):
        try:
            hw.close_serial()
        except Exception:
            pass
        event.accept()


def run_standalone():
    app = QtWidgets.QApplication(sys.argv)
    win = AnyGrowMainWindow()
    win.show()
    win.try_init_serial()
    win.start_timers()
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_standalone()