# ui/main_window.py
# AnyGrow2 PyQt GUI (Refactored)

import sys
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from drivers import hardware as hw
from core import schedule_logic as sched

from ui.widgets.sensor_widget import SensorWidget
from ui.widgets.schedule_widget import ScheduleWidget
from ui.widgets.raw_data_widget import RawDataWidget
from ui.widgets.control_widget import ControlWidget

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AnyGrow2 PyQt GUI")
        self.resize(1050, 550)
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self._last_valid_co2 = None
        self._last_console_print_time = 0.0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(10, 8, 10, 8)
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
        self.schedule_widget = ScheduleWidget()
        self.raw_data_widget = RawDataWidget()
        left_panel.addWidget(self.sensor_widget, 0)
        left_panel.addWidget(self.schedule_widget, 0)
        left_panel.addWidget(self.raw_data_widget, 0)
        left_panel.addStretch(1)
        main_row.addLayout(left_panel, 1)

        # Right panel
        self.control_widget = ControlWidget()
        main_row.addWidget(self.control_widget, 0)

        # =============================
        # Connect Signals
        # =============================
        self.control_widget.led_command.connect(self.send_led_command)
        self.control_widget.brightness_command.connect(self.apply_brightness_from_gui)
        self.control_widget.pump_command.connect(self.send_pump_command)
        self.control_widget.uv_command.connect(self.send_uv_command)

        self.schedule_widget.apply_schedule.connect(self.apply_manual_schedule)
        self.schedule_widget.schedule_enabled_changed.connect(self.apply_schedule_now)
        
        # =============================
        # Timers
        # =============================
        self.poll_timer = QtCore.QTimer(self)
        self.poll_timer.setInterval(200)
        self.poll_timer.timeout.connect(self.poll_serial)

        self.schedule_timer = QtCore.QTimer(self)
        self.schedule_timer.setInterval(30000)
        self.schedule_timer.timeout.connect(self.schedule_tick)

    def _setup_top_bar(self, root_layout):
        top_bar = QtWidgets.QHBoxLayout()
        root_layout.addLayout(top_bar)

        lbl_serial_title = QtWidgets.QLabel("시리얼 상태:")
        lbl_serial_title.setStyleSheet("font-weight: bold;")
        self.lbl_serial_status = QtWidgets.QLabel("프로그램 시작")

        lbl_req_title = QtWidgets.QLabel("   센서 요청 횟수:")
        lbl_req_title.setStyleSheet("margin-left: 10px;")
        self.lbl_req_count = QtWidgets.QLabel("0")

        top_bar.addWidget(lbl_serial_title)
        top_bar.addWidget(self.lbl_serial_status)
        top_bar.addWidget(lbl_req_title)
        top_bar.addWidget(self.lbl_req_count)
        top_bar.addStretch(1)

        self.btn_reconnect = QtWidgets.QPushButton("시리얼 재연결")
        self.btn_reconnect.clicked.connect(self.reconnect_serial)
        top_bar.addWidget(self.btn_reconnect)

    # ============================================================
    # UI Helpers
    # ============================================================
    def _show_error(self, title: str, msg: str):
        QtWidgets.QMessageBox.critical(self, title, msg)

    def set_serial_status(self, text: str):
        self.lbl_serial_status.setText(text)

    def set_request_count(self, n: int):
        self.lbl_req_count.setText(str(n))

    # ============================================================
    # Hardware Control Slots
    # ============================================================
    def send_led_command(self, mode: str):
        try:
            hw.send_led_packet(mode)
            self.set_serial_status(f"LED 명령 전송: {mode}")
        except Exception as e:
            self.set_serial_status(f"[ERROR] LED 전송 실패: {e}")
            self._show_error("LED Error", str(e))

    def send_pump_command(self, on: bool):
        try:
            hw.send_pump(on)
            self.set_serial_status(f"양액 펌프: {'On' if on else 'Off'} 명령 전송")
        except Exception as e:
            self.set_serial_status(f"[ERROR] 펌프 명령 실패: {e}")
            self._show_error("Pump Error", str(e))

    def send_uv_command(self, on: bool):
        try:
            hw.send_uv(on)
            self.set_serial_status(f"UV 필터: {'On' if on else 'Off'} 명령 전송")
        except Exception as e:
            self.set_serial_status(f"[ERROR] UV 명령 실패: {e}")
            self._show_error("UV Error", str(e))

    def apply_brightness_from_gui(self, levels: list):
        try:
            hw.apply_brightness_levels(levels)
            self.set_serial_status(f"[BRIGHT] 7 라인 밝기 적용 요청: {levels}")
        except Exception as e:
            self.set_serial_status(f"[ERROR] 밝기 적용 실패: {e}")
            self._show_error("Brightness Error", str(e))

    # ============================================================
    # Schedule Logic Slots
    # ============================================================
    def apply_manual_schedule(self, entries: list):
        try:
            sched.set_schedule(entries)
        except ValueError as e:
            self._show_error("시간 형식 오류", str(e))
            return

        self.schedule_widget.set_status_text(f"스케줄 {len(entries)}개 구간 적용됨")
        self.schedule_widget.set_enabled(True)
        self.apply_schedule_now()

    def apply_schedule_now(self):
        if not self.schedule_widget.is_enabled():
            self.schedule_widget.set_status_text("스케줄 사용 안 함")
            return

        mode = sched.get_mode_for_now()
        if mode is None:
            self.schedule_widget.set_status_text("스케줄 없음")
            return

        try:
            hw.send_led_packet(mode)
            self.schedule_widget.set_status_text(
                f"현재 시간 기준 모드 적용: {mode} ({datetime.now().strftime('%H:%M')})"
            )
        except Exception as e:
            self.schedule_widget.set_status_text(f"[ERROR] 스케줄 적용 실패: {e}")
            self._show_error("Schedule Error", str(e))

    def schedule_tick(self):
        try:
            if self.schedule_widget.is_enabled():
                mode = sched.get_mode_for_now()
                if mode is not None:
                    hw.send_led_packet(mode)
                    self.schedule_widget.set_status_text(
                        f"자동 스케줄 적용 중: {mode} ({datetime.now().strftime('%H:%M')})"
                    )
                else:
                    self.schedule_widget.set_status_text("스케줄 없음")
            else:
                self.schedule_widget.set_status_text("스케줄 사용 안 함")
        except Exception as e:
            self.schedule_widget.set_status_text(f"[ERROR] 자동 스케줄 실패: {e}")

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
        if not self.schedule_timer.isActive():
            self.schedule_timer.start()
        QtCore.QTimer.singleShot(1000, self.schedule_tick)

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
