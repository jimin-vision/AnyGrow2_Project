# ui/main_window.py
import sys
import time
from datetime import datetime

from PyQt5 import QtCore, QtGui, QtWidgets

from ui.widgets.sensor_widget import SensorWidget
from ui.widgets.raw_data_widget import RawDataWidget
from ui.widgets.control_widget import ControlWidget
from ui.widgets.schedule_widget import ScheduleWidget

# 센서 데이터가 마지막으로 수신된 후 타임아웃으로 간주할 시간 (초)
SENSOR_DATA_TIMEOUT = 5.0

class AnyGrowMainWindow(QtWidgets.QMainWindow):
    """
    AnyGrow2 애플리케이션의 메인 윈도우 클래스입니다.
    모든 UI 컴포넌트를 조립하고 애플리케이션의 핵심 로직에 연결하는 역할을 합니다.
    """
    def __init__(self, app_state, main_controller, hardware_manager, scheduler):
        """
        메인 윈도우를 초기화합니다.
        
        Args:
            app_state (AppState): 애플리케이션의 상태를 저장하는 객체입니다.
            main_controller (MainController): 애플리케이션의 메인 컨트롤러입니다.
            hardware_manager (HardwareManager): 하드웨어 통신을 관리하는 객체입니다.
            scheduler (Scheduler): 예약된 작업을 실행하는 스케줄러입니다.
        """
        super().__init__()

        self._app_state = app_state
        self._main_controller = main_controller
        self._hardware_manager = hardware_manager
        self._scheduler = scheduler

        self.setWindowTitle("AnyGrow2 PyQt GUI")
        self.setFont(QtGui.QFont("Malgun Gothic", 9))

        self._last_data_timestamp = 0

        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        root_layout = QtWidgets.QVBoxLayout(central)
        root_layout.setContentsMargins(10, 2, 10, 2)
        root_layout.setSpacing(8)

        self._setup_ui(root_layout)
        
        self.setFixedSize(int(self.sizeHint().width() * 1.1), int(self.sizeHint().height() * 1.0))
        
        self._connect_signals()
        self._start_ui_timers()

    def _setup_ui(self, root_layout):
        """메인 UI 레이아웃을 설정합니다."""
        self._setup_top_bar(root_layout)
        
        main_row = QtWidgets.QHBoxLayout()
        root_layout.addLayout(main_row, 1)

        # 왼쪽 패널: 센서 데이터 및 예약 설정
        left_panel = QtWidgets.QVBoxLayout()
        left_panel.setSpacing(8)
        self.sensor_widget = SensorWidget()
        self.raw_data_widget = RawDataWidget()
        self._setup_schedule_controls()
        
        left_panel.addWidget(self.sensor_widget, 0)
        left_panel.addWidget(self.raw_data_widget, 1)
        left_panel.addWidget(self.gb_schedule)
        left_panel.addStretch(2)
        main_row.addLayout(left_panel, 1)

        # 오른쪽 패널: 수동 제어
        self.control_widget = ControlWidget()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.control_widget)
        main_row.addWidget(scroll_area, 0)

    def _setup_top_bar(self, root_layout):
        """상단 상태 바를 설정합니다."""
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

    def _setup_schedule_controls(self):
        """UI의 예약 설정 섹션을 설정합니다."""
        self.gb_schedule = QtWidgets.QGroupBox("예약 설정")
        root_v_layout = QtWidgets.QVBoxLayout(self.gb_schedule)
        self.schedule_widget = ScheduleWidget()
        root_v_layout.addWidget(self.schedule_widget)
        
    def _start_ui_timers(self):
        """UI 업데이트를 위한 타이머를 시작합니다."""
        # 메인 시계용 타이머
        self.clock_timer = QtCore.QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()

        # 센서 데이터 수신 시간 확인용 타이머
        self.sensor_status_timer = QtCore.QTimer(self)
        self.sensor_status_timer.setInterval(1000)
        self.sensor_status_timer.timeout.connect(self._check_sensor_data_age)
        self.sensor_status_timer.start()
        
    def _connect_signals(self):
        """위젯 및 컨트롤러의 시그널을 메인 윈도우의 슬롯에 연결합니다."""
        # 수동 제어 위젯 시그널
        self.control_widget.led_command.connect(self.send_led_command)
        self.control_widget.channel_led_command.connect(self.apply_channel_led_from_gui)
        self.control_widget.pump_command.connect(self.send_pump_command)
        self.control_widget.uv_command.connect(self.send_uv_command)
        self.control_widget.bms_time_sync_command.connect(self.sync_bms_time)
        
        # 하드웨어 매니저 시그널
        self._hardware_manager.status_changed.connect(self.set_serial_status)
        self._hardware_manager.raw_string_updated.connect(self.raw_data_widget.set_text)
        self._hardware_manager.request_sent.connect(self._increment_request_count)

        # 메인 컨트롤러 및 앱 상태 시그널
        self.btn_reconnect.clicked.connect(self._main_controller.reconnect_hardware)
        self._app_state.data_updated.connect(self._on_app_state_updated)
        
        # 스케줄러 시그널
        self.schedule_widget.schedules_updated.connect(self._scheduler.update_schedules)
        self._scheduler.schedules_loaded.connect(self.schedule_widget.load_schedules)
        self._scheduler.schedule_status_updated.connect(self.set_serial_status)

    @QtCore.pyqtSlot(dict)
    def _on_app_state_updated(self, data: dict):
        """센서 데이터가 업데이트될 때 UI를 새로고침하는 슬롯."""
        self.sensor_widget.update_sensor_bars(data)
        self._last_data_timestamp = time.time()

    @QtCore.pyqtSlot(str)
    def set_serial_status(self, text: str):
        """시리얼 상태 라벨의 텍스트를 설정합니다."""
        self.lbl_serial_status.setText(text)
    
    @QtCore.pyqtSlot()
    def _increment_request_count(self):
        """센서 요청 카운터를 1 증가시킵니다."""
        try:
            cnt = int(self.lbl_req_count.text()) + 1
        except ValueError:
            cnt = 1
        self.lbl_req_count.setText(str(cnt))

    def _check_sensor_data_age(self):
        """마지막 데이터 수신 후 경과 시간을 확인하고 상태 라벨을 업데이트합니다."""
        if self._last_data_timestamp == 0:
            self.sensor_widget.set_sensor_status_text("센서 데이터 수신 기록 없음")
            return
        
        age_sec = time.time() - self._last_data_timestamp
        if age_sec < SENSOR_DATA_TIMEOUT:
            self.sensor_widget.set_sensor_status_text(f"센서 통신 정상 (마지막 수신 {age_sec:4.1f}초 전)")
        else:
            self.sensor_widget.set_sensor_status_text(f"⚠ 센서 데이터 안 들어옴 (마지막 수신 {age_sec:4.1f}초 전)")
            
    def _update_clock(self):
        """메인 시계 표시를 업데이트합니다."""
        now_str = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        self.lbl_current_time.setText(now_str)

    def _send_command(self, command_type: str, params: dict, status_message: str):
        """메인 컨트롤러에 명령을 보내는 헬퍼 메서드."""
        print(f"[UI 동작] {command_type} 명령 전송: {params}")
        self.set_serial_status(status_message)
        self._main_controller.send_command(command_type, params)
        
    @QtCore.pyqtSlot(str)
    def send_led_command(self, mode: str):
        """메인 LED를 제어하는 명령을 보냅니다."""
        self._send_command('led', {'mode': mode}, f"LED 명령 예약: {mode}")

    @QtCore.pyqtSlot(bool)
    def send_pump_command(self, on: bool):
        """펌프를 제어하는 명령을 보냅니다."""
        status = 'On' if on else 'Off'
        self._send_command('pump', {'on': on}, f"양액 펌프 명령 예약: {status}")

    @QtCore.pyqtSlot(bool)
    def send_uv_command(self, on: bool):
        """UV 필터를 제어하는 명령을 보냅니다."""
        status = 'On' if on else 'Off'
        self._send_command('uv', {'on': on}, f"UV 필터 명령 예약: {status}")

    @QtCore.pyqtSlot(list)
    def apply_channel_led_from_gui(self, settings: list):
        """개별 LED 채널의 속성을 설정하는 명령을 보냅니다."""
        self._send_command('channel_led', {'settings': settings}, f"채널별 LED 설정 명령 예약")

    @QtCore.pyqtSlot(datetime)
    def sync_bms_time(self, dt: datetime):
        """BMS 시간을 동기화하는 명령을 보냅니다."""
        time_data = {'hour': dt.hour, 'minute': dt.minute, 'second': dt.second}
        self._send_command('bms_time_sync', time_data, f"BMS 시간 동기화 명령 예약: {dt.strftime('%H:%M:%S')}")
        self.control_widget.update_bms_display(dt)

    def closeEvent(self, event):
        """윈도우 종료 이벤트를 처리하여 하드웨어 스레드를 중지합니다."""
        self._main_controller.stop_hardware()
        event.accept()

def run_standalone():
    """테스트 목적으로 윈도우를 단독으로 실행하는 함수."""
    app = QtWidgets.QApplication(sys.argv)
    # 이 윈도우는 메인 컨트롤러 및 다른 구성 요소에 의존하므로 단독으로 실행할 수 없습니다.
    print("이 윈도우는 단독으로 실행할 수 없습니다. app.py를 실행하세요.")

if __name__ == "__main__":
    run_standalone()