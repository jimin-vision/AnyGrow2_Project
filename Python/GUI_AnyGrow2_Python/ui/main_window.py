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
from ui.widgets.interval_widget import IntervalWidget

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AnyGrow2 PyQt GUI")
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self._last_valid_co2 = None
        self._last_console_print_time = 0.0
        self.interval_widgets = []
        self.active_timers = []

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
        left_panel.addWidget(self.raw_data_widget, 1) # 1/3 of the stretch space
        left_panel.addWidget(self.gb_timer) 
        left_panel.addStretch(2) # 2/3 of the stretch space
        main_row.addLayout(left_panel, 1)

        # Right panel (with scroll)
        self.control_widget = ControlWidget()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.control_widget)
        main_row.addWidget(scroll_area, 0)

        # Calculate optimal size and set fixed size
        optimal_size = self.sizeHint()
        self.setFixedSize(int(optimal_size.width() * 0.95), int(optimal_size.height() * 1.2))

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

        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)

    def _setup_top_bar(self, root_layout):
        top_bar = QtWidgets.QHBoxLayout()
        root_layout.addLayout(top_bar)

        self.btn_reconnect = QtWidgets.QPushButton("시리얼 재연결")
        self.btn_reconnect.clicked.connect(self.reconnect_serial)
        
        lbl_req_title = QtWidgets.QLabel("센서 요청 횟수:")
        self.lbl_req_count = QtWidgets.QLabel("0")

        lbl_serial_title = QtWidgets.QLabel("시리얼 상태:")
        lbl_serial_title.setStyleSheet("font-weight: bold;")
        self.lbl_serial_status = QtWidgets.QLabel("프로그램 시작")
        self.lbl_serial_status.setWordWrap(True)

        self.lbl_current_time = QtWidgets.QLabel("HH:MM:SS")
        font = self.lbl_current_time.font()
        font.setBold(True)
        self.lbl_current_time.setFont(font)
        
        top_bar.addWidget(self.btn_reconnect)
        top_bar.addWidget(lbl_req_title)
        top_bar.addWidget(self.lbl_req_count)
        top_bar.addSpacing(20)
        top_bar.addWidget(lbl_serial_title)
        top_bar.addWidget(self.lbl_serial_status, 1) # Add with stretch
        top_bar.addWidget(self.lbl_current_time)

    def _update_clock(self):
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        self.lbl_current_time.setText(now_str)
        
    def _setup_timer_controls(self):
        self.gb_timer = QtWidgets.QGroupBox("구간별 동작 설정")
        
        root_v_layout = QtWidgets.QVBoxLayout(self.gb_timer)

        # Scroll Area for intervals
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        self.intervals_layout = QtWidgets.QVBoxLayout(scroll_widget)
        self.intervals_layout.setSpacing(4)
        self.intervals_layout.addStretch(1)
        scroll_area.setWidget(scroll_widget)
        
        # Set a reasonable minimum height for the scroll area
        scroll_area.setMinimumHeight(150)

        # Buttons at the bottom
        btn_layout = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("✚ 구간 추가")
        btn_add.clicked.connect(self._add_interval_row)
        btn_apply = QtWidgets.QPushButton("💾 모든 예약 적용")
        btn_apply.clicked.connect(self.apply_all_schedules)
        btn_layout.addWidget(btn_add)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_apply)

        root_v_layout.addWidget(scroll_area)
        root_v_layout.addLayout(btn_layout)
        
        # Add one interval by default
        self._add_interval_row()

    def _add_interval_row(self):
        new_interval = IntervalWidget()
        new_interval.remove_requested.connect(lambda: self._remove_interval_row(new_interval))
        
        # Insert before the stretch
        self.intervals_layout.insertWidget(self.intervals_layout.count() - 1, new_interval)
        self.interval_widgets.append(new_interval)
        self._update_interval_numbers()

    def _remove_interval_row(self, widget_to_remove):
        if widget_to_remove in self.interval_widgets:
            self.interval_widgets.remove(widget_to_remove)
            self.intervals_layout.removeWidget(widget_to_remove)
            widget_to_remove.deleteLater()
            self._update_interval_numbers()

    def _update_interval_numbers(self):
        for i, widget in enumerate(self.interval_widgets):
            widget.set_number(i + 1)

    # ============================================================
    # UI Helpers
    # ============================================================
    def _show_error(self, title: str, msg: str):
        QtWidgets.QMessageBox.critical(self, title, msg)

    def set_serial_status(self, text: str):
        self.lbl_serial_status.setText(text)
        self.lbl_serial_status.setToolTip(text)

    def set_request_count(self, n: int):
        self.lbl_req_count.setText(str(n))

    # ============================================================
    # Hardware Control Slots
    # ============================================================
    def send_led_command(self, mode: str):
        self.set_serial_status(f"LED 명령 전송: {mode}")
        hw.submit_command('led', mode)

    def send_pump_command(self, on: bool):
        status = 'On' if on else 'Off'
        self.set_serial_status(f"양액 펌프 명령 전송: {status}")
        hw.submit_command('pump', on)

    def send_uv_command(self, on: bool):
        status = 'On' if on else 'Off'
        self.set_serial_status(f"UV 필터 명령 전송: {status}")
        hw.submit_command('uv', on)

    def apply_channel_led_from_gui(self, settings: list):
        self.set_serial_status(f"채널별 LED 설정 명령 전송: {settings}")
        hw.submit_command('channel_led', settings)

    def sync_bms_time(self):
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        self.set_serial_status(f"BMS 시간 동기화 명령 전송: {hour:02d}:{minute:02d}")
        hw.submit_command('bms_time_sync', (hour, minute))

    def apply_all_schedules(self):
        # 1. Cancel all previously scheduled timers
        for timer in self.active_timers:
            timer.stop()
        self.active_timers.clear()
        
        self.set_serial_status("기존 예약을 모두 취소하고 새 예약을 적용합니다...")
        
        current_time = QtCore.QTime.currentTime()
        schedule_count = 0

        # 2. Iterate through widgets and create new timers
        for i, widget in enumerate(self.interval_widgets):
            settings = widget.get_values()
            start_time = settings["start_time"]
            end_time = settings["end_time"]
            action = settings["action"]
            target = settings["target"]

            is_on_at_start = (action == "켜기 (ON)")

            # --- Schedule start action ---
            msecs_until_start = current_time.msecsTo(start_time)
            if msecs_until_start < 0:
                msecs_until_start += 24 * 60 * 60 * 1000 # Next day
            
            start_timer = QtCore.QTimer(self)
            start_timer.setSingleShot(True)
            
            start_func = self._get_command_func(target, is_on_at_start)
            if start_func:
                start_timer.timeout.connect(start_func)
                start_timer.start(msecs_until_start)
                self.active_timers.append(start_timer)
                schedule_count += 1

            # --- Schedule end action (opposite of start) ---
            msecs_until_end = current_time.msecsTo(end_time)
            if msecs_until_end < 0:
                msecs_until_end += 24 * 60 * 60 * 1000 # Next day

            # Handle case where end time is before start time (overnight interval)
            if start_time > end_time:
                 # This logic assumes if start > end, it's an overnight task
                 # and the end is on the "next" day relative to the start.
                 pass # msecs_until_end is already correct for the next day if past

            end_timer = QtCore.QTimer(self)
            end_timer.setSingleShot(True)

            end_func = self._get_command_func(target, not is_on_at_start)
            if end_func:
                end_timer.timeout.connect(end_func)
                end_timer.start(msecs_until_end)
                self.active_timers.append(end_timer)
                schedule_count += 1
        
        self.set_serial_status(f"총 {schedule_count}개의 예약(켜기/끄기)을 설정했습니다.")

    def _get_command_func(self, target: str, is_on: bool):
        """Helper to get the correct hardware command function."""
        if target == "전체 LED":
            mode = "Auto" if is_on else "Off"
            return lambda: self.send_led_command(mode)
        elif target == "양액 펌프":
            return lambda: self.send_pump_command(is_on)
        elif target == "UV 필터":
            return lambda: self.send_uv_command(is_on)
        return None

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
        if not self.clock_timer.isActive():
            self.clock_timer.start()

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