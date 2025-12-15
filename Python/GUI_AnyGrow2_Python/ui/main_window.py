# ui/main_window.py
import sys
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from drivers.hardware import HardwareManager
from ui.widgets.sensor_widget import SensorWidget
from ui.widgets.raw_data_widget import RawDataWidget
from ui.widgets.control_widget import ControlWidget
from ui.widgets.interval_widget import IntervalWidget

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("AnyGrow2 PyQt GUI (Refactored)")
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self.interval_widgets = []
        self.active_timers = []
        self._last_valid_co2 = None
        self._last_data_timestamp = 0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(10, 2, 10, 2)
        root_layout.setSpacing(8)

        self._setup_ui(root_layout)
        
        self.setFixedSize(int(self.sizeHint().width() * 1.05), int(self.sizeHint().height() * 0.95))
        
        self._connect_signals()
        self._start_hardware_thread()
        self._start_ui_timers()

    def _setup_ui(self, root_layout):
        self._setup_top_bar(root_layout)
        
        main_row = QtWidgets.QHBoxLayout()
        root_layout.addLayout(main_row, 1)

        # Left panel
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(8)
        self.sensor_widget = SensorWidget()
        self.raw_data_widget = RawDataWidget()
        self._setup_timer_controls()
        
        left_panel.addWidget(self.sensor_widget, 0)
        left_panel.addWidget(self.raw_data_widget, 1)
        left_panel.addWidget(self.gb_timer)
        left_panel.addStretch(2)
        main_row.addLayout(left_panel, 1)

        # Right panel
        self.control_widget = ControlWidget()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.control_widget)
        main_row.addWidget(scroll_area, 0)

    def _setup_top_bar(self, root_layout):
        top_bar = QtWidgets.QHBoxLayout()
        root_layout.addLayout(top_bar)

        self.btn_reconnect = QtWidgets.QPushButton("시리얼 재연결")
        
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
        top_bar.addWidget(self.lbl_serial_status, 1)
        top_bar.addWidget(self.lbl_current_time)

    def _setup_timer_controls(self):
        self.gb_timer = QtWidgets.QGroupBox("구간별 동작 설정")
        root_v_layout = QtWidgets.QVBoxLayout(self.gb_timer)
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()
        self.intervals_layout = QtWidgets.QVBoxLayout(scroll_widget)
        self.intervals_layout.setSpacing(4)
        self.intervals_layout.addStretch(1)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setMinimumHeight(200)

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
        self._add_interval_row()
        
    def _start_hardware_thread(self):
        self.hw_thread = QtCore.QThread()
        self.hw_manager = HardwareManager()
        self.hw_manager.moveToThread(self.hw_thread)

        # Connect signals from worker to GUI
        self.hw_manager.status_changed.connect(self.set_serial_status)
        self.hw_manager.data_updated.connect(self._on_data_updated)
        self.hw_manager.raw_string_updated.connect(self.raw_data_widget.set_text)
        self.hw_manager.request_sent.connect(self._increment_request_count)
        # Manually trigger a reconnect attempt using a thread-safe call
        self.btn_reconnect.clicked.connect(
            lambda: QtCore.QMetaObject.invokeMethod(self.hw_manager, "reconnect", QtCore.Qt.QueuedConnection)
        )

        # Connect thread management signals
        self.hw_thread.started.connect(self.hw_manager.start)
        self.hw_thread.finished.connect(self.hw_manager.deleteLater)
        
        self.hw_thread.start()

    def _start_ui_timers(self):
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()

        self.sensor_status_timer = QtCore.QTimer(self)
        self.sensor_status_timer.setInterval(1000)
        self.sensor_status_timer.timeout.connect(self._check_sensor_status)
        self.sensor_status_timer.start()
        
    def _connect_signals(self):
        self.control_widget.led_command.connect(self.send_led_command)
        self.control_widget.channel_led_command.connect(self.apply_channel_led_from_gui)
        self.control_widget.pump_command.connect(self.send_pump_command)
        self.control_widget.uv_command.connect(self.send_uv_command)
        self.control_widget.bms_time_sync_command.connect(self.sync_bms_time)

    # ============================================================
    # UI Update Slots (connected to signals from HardwareManager)
    # ============================================================
    @QtCore.pyqtSlot(str)
    def set_serial_status(self, text: str):
        self.lbl_serial_status.setText(text)
    
    @QtCore.pyqtSlot()
    def _increment_request_count(self):
        try:
            cnt = int(self.lbl_req_count.text()) + 1
        except ValueError:
            cnt = 1
        self.lbl_req_count.setText(str(cnt))

    @QtCore.pyqtSlot(dict)
    def _on_data_updated(self, data: dict):
        self._last_data_timestamp = data.get('timestamp', 0)
        t = data.get('temp')
        h = data.get('humidity')
        c = data.get('co2')
        il = data.get('illum')

        # CO2 sensor spike filtering
        if c is not None and c >= 6000:
            c = self._last_valid_co2 if self._last_valid_co2 is not None else 0
        else:
            self._last_valid_co2 = c

        self.sensor_widget.update_sensor_bars(t, h, int(c or 0), int(il or 0))
        self.sensor_widget.set_last_update_text(datetime.now().strftime("마지막 갱신: %H:%M:%S"))

    def _check_sensor_status(self):
        if self._last_data_timestamp == 0:
            self.sensor_widget.set_sensor_status_text("센서 데이터 수신 기록 없음")
            return
        
        age_sec = time.time() - self._last_data_timestamp
        if age_sec < 5.0:
            self.sensor_widget.set_sensor_status_text(f"센서 통신 정상 (마지막 수신 {age_sec:4.1f}초 전)")
        else:
            self.sensor_widget.set_sensor_status_text(f"⚠ 센서 데이터 안 들어옴 (마지막 수신 {age_sec:4.1f}초 전)")
            
    def _update_clock(self):
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        self.lbl_current_time.setText(now_str)
        
    # ============================================================
    # Command Sending Slots (sends commands to HardwareManager)
    # ============================================================
    def _send_command_to_worker(self, cmd, *args):
        # Use invokeMethod for thread-safe slot calling
        arg_list = list(args)
        QtCore.QMetaObject.invokeMethod(
            self.hw_manager,
            "submit_command",
            QtCore.Qt.QueuedConnection,
            QtCore.Q_ARG(str, cmd),
            QtCore.Q_ARG(object, arg_list or None)
        )

    @QtCore.pyqtSlot(str)
    def send_led_command(self, mode: str):
        self.set_serial_status(f"LED 명령 예약: {mode}")
        self._send_command_to_worker('led', mode)

    @QtCore.pyqtSlot(bool)
    def send_pump_command(self, on: bool):
        status = 'On' if on else 'Off'
        self.set_serial_status(f"양액 펌프 명령 예약: {status}")
        self._send_command_to_worker('pump', on)

    @QtCore.pyqtSlot(bool)
    def send_uv_command(self, on: bool):
        status = 'On' if on else 'Off'
        self.set_serial_status(f"UV 필터 명령 예약: {status}")
        self._send_command_to_worker('uv', on)

    @QtCore.pyqtSlot(list)
    def apply_channel_led_from_gui(self, settings: list):
        self.set_serial_status(f"채널별 LED 설정 명령 예약: {settings}")
        # self._send_command_to_worker('channel_led', settings) # Not implemented yet

    @QtCore.pyqtSlot()
    def sync_bms_time(self):
        now = datetime.now()
        self.set_serial_status(f"BMS 시간 동기화 명령 예약: {now.hour:02d}:{now.minute:02d}:{now.second:02d}")
        self._send_command_to_worker('bms_time_sync', now.hour, now.minute, now.second)

    def apply_all_schedules(self):
        for timer in self.active_timers:
            timer.stop()
        self.active_timers.clear()
        
        self.set_serial_status("기존 예약을 모두 취소하고 새 예약을 적용합니다...")
        current_time = QtCore.QTime.currentTime()
        schedule_count = 0

        for widget in self.interval_widgets:
            settings = widget.get_values()
            if not settings["start_time"].isValid(): continue
            
            start_time = settings["start_time"]
            end_time = settings["end_time"]
            is_on_at_start = (settings["action"] == "켜기 (ON)")
            
            # --- Schedule Start Action ---
            msecs_until_start = current_time.msecsTo(start_time)
            if msecs_until_start < 0: msecs_until_start += 24 * 60 * 60 * 1000
            
            start_timer = QtCore.QTimer(self)
            start_timer.setSingleShot(True)
            start_timer.timeout.connect(self._get_command_func(settings["target"], is_on_at_start))
            start_timer.start(msecs_until_start)
            self.active_timers.append(start_timer)
            schedule_count += 1
            
            # --- Schedule End Action ---
            msecs_until_end = current_time.msecsTo(end_time)
            if msecs_until_end < 0: msecs_until_end += 24 * 60 * 60 * 1000
            
            end_timer = QtCore.QTimer(self)
            end_timer.setSingleShot(True)
            end_timer.timeout.connect(self._get_command_func(settings["target"], not is_on_at_start))
            end_timer.start(msecs_until_end)
            self.active_timers.append(end_timer)
            schedule_count += 1
        
        self.set_serial_status(f"총 {schedule_count}개의 예약(켜기/끄기)을 설정했습니다.")

    def _get_command_func(self, target: str, is_on: bool):
        if target == "전체 LED":
            mode = "Auto" if is_on else "Off"
            return lambda: self.send_led_command(mode)
        elif target == "양액 펌프":
            return lambda: self.send_pump_command(is_on)
        elif target == "UV 필터":
            return lambda: self.send_uv_command(is_on)
        return lambda: None

    # ============================================================
    # Interval Widget Management
    # ============================================================
    def _add_interval_row(self):
        new_interval = IntervalWidget()
        new_interval.remove_requested.connect(lambda: self._remove_interval_row(new_interval))
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
            
    def closeEvent(self, event):
        self.hw_manager.stop()
        self.hw_thread.quit()
        self.hw_thread.wait(2000) # Wait up to 2s for thread to finish
        event.accept()

def run_standalone():
    app = QtWidgets.QApplication(sys.argv)
    win = AnyGrowMainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_standalone()