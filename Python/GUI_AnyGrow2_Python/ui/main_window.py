# ui/main_window.py
import sys
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from ui.widgets.sensor_widget import SensorWidget
from ui.widgets.raw_data_widget import RawDataWidget
from ui.widgets.control_widget import ControlWidget
from ui.widgets.interval_widget import IntervalWidget

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    def __init__(self, app_state, main_controller, hardware_manager):
        super().__init__()

        self._app_state = app_state
        self._main_controller = main_controller
        self._hardware_manager = hardware_manager # app.py에서 인스턴스를 받으므로 직접 생성하지 않습니다.

        self.setWindowTitle("AnyGrow2 PyQt GUI (Refactored)")
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self.interval_widgets = []
        self._last_data_timestamp = 0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(10, 2, 10, 2)
        root_layout.setSpacing(8)

        self._setup_ui(root_layout)
        
        self.setFixedSize(int(self.sizeHint().width() * 1.05), int(self.sizeHint().height() * 0.95))
        
        self._connect_signals()
        # _start_hardware_thread() 호출 제거
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
        
    def _start_ui_timers(self):
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()

        # 데이터 수신 상태를 주기적으로 확인하기 위한 타이머
        self.sensor_status_timer = QtCore.QTimer(self)
        self.sensor_status_timer.setInterval(1000)
        self.sensor_status_timer.timeout.connect(self._check_sensor_data_age)
        self.sensor_status_timer.start()
        
    def _connect_signals(self):
        self.control_widget.led_command.connect(self.send_led_command)
        self.control_widget.channel_led_command.connect(self.apply_channel_led_from_gui)
        self.control_widget.pump_command.connect(self.send_pump_command)
        self.control_widget.uv_command.connect(self.send_uv_command)
        self.control_widget.bms_time_sync_command.connect(self.sync_bms_time)
        
        # HardwareManager의 status_changed 시그널을 직접 수신
        self._hardware_manager.status_changed.connect(self.set_serial_status)
        # raw_data_widget은 여전히 raw 데이터를 직접 수신
        self._hardware_manager.raw_string_updated.connect(self.raw_data_widget.set_text)
        self._hardware_manager.request_sent.connect(self._increment_request_count)

        # 재연결 버튼 클릭 시 MainController를 통해 하드웨어 재연결 요청
        self.btn_reconnect.clicked.connect(self._main_controller.reconnect_hardware)

        # AppState의 데이터 변경 시그널을 UI 업데이트 슬롯에 연결
        self._app_state.data_updated.connect(self._on_app_state_updated)
        
        # MainController의 스케줄링 상태 업데이트 시그널 연결
        self._main_controller.schedule_status_updated.connect(self.set_serial_status)


    # ============================================================
    # UI Update Slots (connected to signals from HardwareManager)
    # ============================================================
    @QtCore.pyqtSlot(dict)
    def _on_app_state_updated(self, data: dict):
        """센서 데이터가 업데이트될 때 UI를 새로고침하는 슬롯"""
        self.sensor_widget.update_sensor_bars(data)
        self._last_data_timestamp = time.time()

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

    def _check_sensor_data_age(self):
        """마지막 데이터 수신 시간으로부터 경과 시간을 확인하고 상태 라벨을 업데이트합니다."""
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
        
    @QtCore.pyqtSlot(str)
    def send_led_command(self, mode: str):
        print(f"[UI 동작] LED 명령 전송: {mode}")
        self.set_serial_status(f"LED 명령 예약: {mode}")
        self._main_controller.send_command('led', {'mode': mode})

    @QtCore.pyqtSlot(bool)
    def send_pump_command(self, on: bool):
        status = 'On' if on else 'Off'
        print(f"[UI 동작] 양액 펌프 명령 전송: {status}")
        self.set_serial_status(f"양액 펌프 명령 예약: {status}")
        self._main_controller.send_command('pump', {'on': on})

    @QtCore.pyqtSlot(bool)
    def send_uv_command(self, on: bool):
        status = 'On' if on else 'Off'
        print(f"[UI 동작] UV 필터 명령 전송: {status}")
        self.set_serial_status(f"UV 필터 명령 예약: {status}")
        self._main_controller.send_command('uv', {'on': on})

    @QtCore.pyqtSlot(list)
    def apply_channel_led_from_gui(self, settings: list):
        print(f"[UI 동작] 채널별 LED 설정 전송: {settings}")
        self.set_serial_status(f"채널별 LED 설정 명령 예약: {settings}")
        self._main_controller.send_command('channel_led', {'settings': settings})

    @QtCore.pyqtSlot()
    def sync_bms_time(self):
        now = datetime.now()
        print(f"[UI 동작] BMS 시간 동기화 전송.")
        self.set_serial_status(f"BMS 시간 동기화 명령 예약: {now.hour:02d}:{now.minute:02d}:{now.second:02d}")
        self._main_controller.send_command('bms_time_sync', {'hour': now.hour, 'minute': now.minute, 'second': now.second})

    def apply_all_schedules(self):
        """
        인터벌 위젯들로부터 스케줄 설정을 추출하여 컨트롤러에 전달합니다.
        """
        print("[UI 동작] 모든 스케줄 적용.")
        schedule_settings = [widget.get_values() for widget in self.interval_widgets]
        self._main_controller.apply_all_schedules(schedule_settings)

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
        # HardwareManager 스레드 정지 처리를 MainController로 위임
        self._main_controller.stop_hardware()
        event.accept()

def run_standalone():
    app = QtWidgets.QApplication(sys.argv)
    win = AnyGrowMainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    run_standalone()