# core/main_controller.py
from PyQt5.QtCore import QObject, pyqtSignal, QTime, QTimer
from datetime import datetime

from core.scheduler import Scheduler

class MainController(QObject):
    """
    MainController는 애플리케이션의 중앙 허브입니다.
    UI, 하드웨어 관리자, 애플리케이션 상태를 연결합니다.
    주요 책임은 다음과 같습니다:
    - UI로부터의 사용자 명령을 하드웨어로 전달합니다.
    - 하드웨어로부터의 센서 데이터를 처리하고 애플리케이션 상태를 업데이트합니다.
    - 하드웨어 통신 스레드의 생명주기를 관리합니다.
    - 스케줄러를 조정합니다.
    """
    reconnect_signal = pyqtSignal()

    def __init__(self, hardware_manager, hardware_thread, app_state, scheduler, parent=None):
        """
        MainController를 초기화합니다.
        
        Args:
            hardware_manager (HardwareManager): 하드웨어 통신을 관리하는 객체입니다.
            hardware_thread (QThread): 하드웨어 관리자가 실행되는 스레드입니다.
            app_state (AppState): 애플리케이션의 상태를 저장하는 객체입니다.
            scheduler (Scheduler): 예약된 작업을 실행하는 스케줄러입니다.
            parent (QObject): 부모 QObject입니다.
        """
        super().__init__(parent)
        print("--- MainController 초기화 ---")
        self._hardware_manager = hardware_manager
        self._hardware_thread = hardware_thread
        self._app_state = app_state
        self._scheduler = scheduler

        self._connect_signals()
        
    def _connect_signals(self):
        """컴포넌트 간의 시그널과 슬롯을 연결합니다."""
        self._hardware_manager.data_updated.connect(self._process_sensor_data)
        self._hardware_thread.started.connect(self._hardware_manager.start)
        self.reconnect_signal.connect(self._hardware_manager.reconnect)
        self._scheduler.job_to_execute.connect(self._execute_job)

    def stop_hardware(self):
        """하드웨어 통신 스레드를 안전하게 중지합니다."""
        print("MainController가 하드웨어 스레드를 중지합니다...")
        self._hardware_manager.stop()
        self._hardware_thread.quit()
        self._hardware_thread.wait(2000)
        print("MainController가 하드웨어 스레드를 중지했습니다.")
        
    def _process_sensor_data(self, data: dict):
        """
        하드웨어로부터 들어오는 센서 데이터를 처리합니다.
        CO2 데이터에 필터를 적용하고 앱 상태를 업데이트합니다.
        """
        processed_data = self._apply_co2_filter(data)
        self._app_state.update_sensor_data(processed_data)
        
    def _apply_co2_filter(self, data: dict) -> dict:
        """
        CO2 센서 값을 부드럽게 만들기 위한 간단한 필터입니다.
        새로운 CO2 값이 이전 값과 크게 다르면 센서 오류일 가능성이 높으므로 이전 값을 사용합니다.
        """
        if 'co2' in data:
            current_co2 = data['co2']
            previous_co2 = self._app_state.co2
            if previous_co2 is not None and abs(current_co2 - previous_co2) > 1000:
                data['co2'] = previous_co2
        return data

    def send_command(self, command_type: str, params: dict = None):
        """
        하드웨어 관리자에게 명령을 보냅니다.
        
        Args:
            command_type (str): 보낼 명령의 유형 (예: 'led', 'pump').
            params (dict): 명령에 대한 매개변수 사전.
        """
        if params is None:
            params = {}
        self._hardware_manager.submit_command(command_type, params)
        
    def reconnect_hardware(self):
        """하드웨어 재연결을 요청하는 시그널을 보냅니다."""
        print("MainController가 하드웨어 재연결을 요청합니다...")
        self.reconnect_signal.emit()

    def _execute_job(self, job: dict):
        """
        스케줄러로부터 작업을 받아 하드웨어에 적절한 명령을 보내 실행합니다.
        
        Args:
            job (dict): 실행할 작업을 나타내는 사전.
        """
        target = job.get("target")
        action = job.get("action")
        is_on = (action == "켜기 (ON)")

        print(f"  - 작업: {target} -> {action}")
        self._scheduler.schedule_status_updated.emit(f"실행 중: {job.get('name', '이름 없는 작업')}")

        if target == "전체 LED":
            mode = "On" if is_on else "Off"
            self.send_command('led', {'mode': mode})
        elif target == "양액 펌프":
            self.send_command('pump', {'on': is_on})
        elif target == "UV 필터":
            self.send_command('uv', {'on': is_on})
        else:
            print(f"    - 알 수 없는 작업 대상: {target}")

			
