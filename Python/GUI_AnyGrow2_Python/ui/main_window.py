# ui/main_window.py
import sys
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from ui.widgets.sensor_widget import SensorWidget
from ui.widgets.raw_data_widget import RawDataWidget
from ui.widgets.control_widget import ControlWidget
# --- MODIFIED IMPORT ---
from ui.widgets.schedule_widget import ScheduleWidget

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    def __init__(self, app_state, main_controller, hardware_manager):
        super().__init__()

        self._app_state = app_state
        self._main_controller = main_controller
        self._hardware_manager = hardware_manager # app.py에서 인스턴스를 받으므로 직접 생성하지 않습니다.

        self.setWindowTitle("AnyGrow2 PyQt GUI (Refactored)")
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self._last_data_timestamp = 0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(10, 2, 10, 2)
        root_layout.setSpacing(8)

        self._setup_ui(root_layout)
        
        # --- MODIFIED WIDTH ---
        self.setFixedSize(int(self.sizeHint().width() * 1.1), int(self.sizeHint().height() * 1.0))
        
        self._connect_signals()
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

    # --- MODIFIED METHOD ---
    def _setup_timer_controls(self):
        self.gb_timer = QtWidgets.QGroupBox("예약 설정") # GroupBox 이름 변경
        root_v_layout = QtWidgets.QVBoxLayout(self.gb_timer)

        self.schedule_widget = ScheduleWidget()
        
        # --- REMOVED APPLY BUTTON ---
        # btn_apply = QtWidgets.QPushButton("💾 모든 예약 적용")
        # btn_apply.clicked.connect(self.apply_all_schedules)
        
        root_v_layout.addWidget(self.schedule_widget)
        # root_v_layout.addWidget(btn_apply)
        
    def _start_ui_timers(self):
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()

        self.sensor_status_timer = QtCore.QTimer(self)
        self.sensor_status_timer.setInterval(1000)
        self.sensor_status_timer.timeout.connect(self._check_sensor_data_age)
        self.sensor_status_timer.start()
        
    def _connect_signals(self):
        # Control widget signals
        self.control_widget.led_command.connect(self.send_led_command)
        self.control_widget.channel_led_command.connect(self.apply_channel_led_from_gui)
        self.control_widget.pump_command.connect(self.send_pump_command)
        self.control_widget.uv_command.connect(self.send_uv_command)
        self.control_widget.bms_time_sync_command.connect(self.sync_bms_time)
        
        # Hardware manager signals
        self._hardware_manager.status_changed.connect(self.set_serial_status)
        self._hardware_manager.raw_string_updated.connect(self.raw_data_widget.set_text)
        self._hardware_manager.request_sent.connect(self._increment_request_count)

        # Main window and controller signals
        self.btn_reconnect.clicked.connect(self._main_controller.reconnect_hardware)
        self._app_state.data_updated.connect(self._on_app_state_updated)
        self._main_controller.schedule_status_updated.connect(self.set_serial_status)

        # --- NEW: Schedule System Connections ---
        self.schedule_widget.schedules_updated.connect(self._main_controller.update_schedules)
        self._main_controller.schedules_loaded.connect(self.schedule_widget.load_schedules)



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

    @QtCore.pyqtSlot(dict)
    def sync_bms_time(self, time_data: dict):
        print(f"[UI 동작] BMS 시간 동기화 전송.")
        self.set_serial_status(f"BMS 시간 동기화 명령 예약: {time_data['hour']:02d}:{time_data['minute']:02d}:{time_data['second']:02d}")
        self._main_controller.send_command('bms_time_sync', time_data)

    def apply_all_schedules(self):
        """
        새로운 스케줄 위젯으로부터 모든 스케줄 설정을 추출하여 컨트롤러에 전달합니다.
        """
        print("[UI 동작] 모든 스케줄 적용.")
        schedule_settings = self.schedule_widget.get_all_schedules()
        # self._main_controller.apply_all_schedules(schedule_settings) # 기능 구현 시 주석 해제
        print(f"적용될 스케줄: {schedule_settings}")


    # ============================================================
    # Interval Widget Management (REMOVED)
    # ============================================================
            
    def closeEvent(self, event):
        self._main_controller.stop_hardware()
        event.accept()

def run_standalone():
    app = QtWidgets.QApplication(sys.argv)
    # Standalone 실행을 위해서는 app_state, main_controller, hardware_manager 목업(mockup) 필요
    # 현재 구조에서는 직접 실행이 어려움. app.py를 통해 실행해야 함.
    print("This window cannot be run standalone. Run app.py.")
    # win = AnyGrowMainWindow()
    # win.show()
    # sys.exit(app.exec_())

if __name__ == "__main__":
    run_standalone()