from PyQt5.QtCore import QObject, pyqtSignal, QTime, QTimer

class MainController(QObject):
    """
    애플리케이션의 핵심 비즈니스 로직을 관리하는 컨트롤러 클래스입니다.
    HardwareManager와 AppState 간의 상호작용을 조율하고,
    센서 데이터 처리, 스케줄링 로직, 하드웨어 명령 전송 등을 담당합니다.
    """
    command_to_hardware = pyqtSignal(str, dict)
    schedule_status_updated = pyqtSignal(str)
    reconnect_signal = pyqtSignal()

    def __init__(self, hardware_manager, hardware_thread, app_state, parent=None):
        super().__init__(parent)
        self._hardware_manager = hardware_manager
        self._hardware_thread = hardware_thread
        self._app_state = app_state
        self.active_timers = []
        
        # HardwareManager의 data_updated 시그널을 수신
        self._hardware_manager.data_updated.connect(self._process_sensor_data)

        # HardwareManager 스레드 관리
        self._hardware_thread.started.connect(self._hardware_manager.start)
        
        # Thread-safe reconnect
        self.reconnect_signal.connect(self._hardware_manager.reconnect)
        
    def stop_hardware(self):
        """
        HardwareManager 스레드를 안전하게 종료합니다.
        """
        print("MainController stopping hardware thread...")
        self._hardware_manager.stop()
        self._hardware_thread.quit()
        self._hardware_thread.wait(2000)
        print("MainController hardware thread stopped.")
        
    def _process_sensor_data(self, data: dict):
        """
        HardwareManager로부터 수신된 센서 데이터를 처리하고 AppState를 업데이트합니다.
        CO2 스파이크 필터링과 같은 비즈니스 로직을 여기에 구현합니다.
        """
        processed_data = self._apply_co2_filter(data)
        self._app_state.update_sensor_data(processed_data)
        
    def _apply_co2_filter(self, data: dict) -> dict:
        """
        CO2 스파이크를 필터링하는 로직입니다.
        """
        if 'co2' in data:
            current_co2 = data['co2']
            previous_co2 = self._app_state.co2
            
            if previous_co2 is not None and abs(current_co2 - previous_co2) > 1000:
                print(f"CO2 spike detected: current={current_co2}, previous={previous_co2}. Filtering out.")
                data['co2'] = previous_co2
        return data

    def send_command(self, command_type: str, params: dict = None):
        """
        HardwareManager에 명령을 보냅니다.
        """
        if params is None:
            params = {}
        self._hardware_manager.submit_command(command_type, params)
        
    def apply_all_schedules(self, schedule_settings: list):
        """
        UI로부터 받은 스케줄 목록을 적용합니다.
        기존 타이머를 모두 취소하고 새로운 타이머를 설정합니다.
        """
        for timer in self.active_timers:
            timer.stop()
        self.active_timers.clear()
        
        self.schedule_status_updated.emit("기존 예약을 모두 취소하고 새 예약을 적용합니다...")
        current_time = QTime.currentTime()
        schedule_count = 0

        # Helper to check if current time is in an interval
        def is_time_in_interval(start, end):
            if start <= end: # Not overnight
                return start <= current_time < end
            else: # Overnight
                return current_time >= start or current_time < end

        for settings in schedule_settings:
            if not settings["start_time"].isValid(): continue
            
            start_time = settings["start_time"]
            end_time = settings["end_time"]
            target = settings["target"]
            is_on_at_start = (settings["action"] == "켜기 (ON)")
            
            # --- 1. Immediate State Application ---
            if is_time_in_interval(start_time, end_time):
                self.schedule_status_updated.emit(f"[{target}] 현재 시간이 설정된 구간 내에 있어 즉시 상태를 적용합니다.")
                command_func = self._get_command_func(target, is_on_at_start)
                if command_func:
                    command_func() # Execute immediately

            # --- 2. Schedule Future Events ---
            # Schedule Start Action
            msecs_until_start = current_time.msecsTo(start_time)
            if msecs_until_start < 0: msecs_until_start += 24 * 60 * 60 * 1000
            
            start_timer = QTimer(self) # Parent to controller
            start_timer.setSingleShot(True)
            start_timer.timeout.connect(self._get_command_func(target, is_on_at_start))
            start_timer.start(msecs_until_start)
            self.active_timers.append(start_timer)
            schedule_count += 1
            
            # Schedule End Action
            msecs_until_end = current_time.msecsTo(end_time)
            if msecs_until_end < 0: msecs_until_end += 24 * 60 * 60 * 1000
            
            end_timer = QTimer(self) # Parent to controller
            end_timer.setSingleShot(True)
            end_timer.timeout.connect(self._get_command_func(target, not is_on_at_start))
            end_timer.start(msecs_until_end)
            self.active_timers.append(end_timer)
            schedule_count += 1
        
        self.schedule_status_updated.emit(f"총 {schedule_count}개의 예약(켜기/끄기)을 설정하고 현재 상태를 적용했습니다.")

    def _get_command_func(self, target: str, is_on: bool):
        if target == "전체 LED":
            mode = "Auto" if is_on else "Off"
            return lambda: self.send_command('led', {'mode': mode})
        elif target == "양액 펌프":
            return lambda: self.send_command('pump', {'on': is_on})
        elif target == "UV 필터":
            return lambda: self.send_command('uv', {'on': is_on})
        return lambda: None
        
    def reconnect_hardware(self):
        """
        HardwareManager에 시리얼 재연결을 요청합니다.
        """
        print("MainController requesting hardware reconnect...")
        self.reconnect_signal.emit()
			
