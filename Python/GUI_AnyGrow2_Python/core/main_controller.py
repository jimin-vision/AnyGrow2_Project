from PyQt5.QtCore import QObject, pyqtSignal, QTime, QTimer
from datetime import datetime
import json
import os
import copy

class MainController(QObject):
    """
    애플리케이션의 핵심 비즈니스 로직을 관리하는 컨트롤러 클래스입니다.
    """
    command_to_hardware = pyqtSignal(str, dict)
    schedule_status_updated = pyqtSignal(str)
    reconnect_signal = pyqtSignal()
    schedules_loaded = pyqtSignal(dict)

    def __init__(self, hardware_manager, hardware_thread, app_state, parent=None):
        print("--- MainController __init__ called ---")
        super().__init__(parent)
        self._hardware_manager = hardware_manager
        self._hardware_thread = hardware_thread
        self._app_state = app_state
        
        self.schedules = {}
        self.schedule_file = "schedules.json"
        self._load_schedules_from_file()

        # --- Corrected Scheduler Engine ---
        self.last_checked_minute = -1
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self._check_schedules)
        self.scheduler_timer.start(1000) # Tick every second
        
        self._hardware_manager.data_updated.connect(self._process_sensor_data)
        self._hardware_thread.started.connect(self._hardware_manager.start)
        self.reconnect_signal.connect(self._hardware_manager.reconnect)
        
    def stop_hardware(self):
        print("MainController stopping hardware thread...")
        self._hardware_manager.stop()
        self._hardware_thread.quit()
        self._hardware_thread.wait(2000)
        print("MainController hardware thread stopped.")
        
    def _process_sensor_data(self, data: dict):
        processed_data = self._apply_co2_filter(data)
        self._app_state.update_sensor_data(processed_data)
        
    def _apply_co2_filter(self, data: dict) -> dict:
        if 'co2' in data:
            current_co2 = data['co2']
            previous_co2 = self._app_state.co2
            if previous_co2 is not None and abs(current_co2 - previous_co2) > 1000:
                data['co2'] = previous_co2
        return data

    def send_command(self, command_type: str, params: dict = None):
        if params is None:
            params = {}
        self._hardware_manager.submit_command(command_type, params)
        
    def reconnect_hardware(self):
        print("MainController requesting hardware reconnect...")
        self.reconnect_signal.emit()

    # ============================================================
    # NEW SCHEDULING LOGIC
    # ============================================================

    def update_schedules(self, schedules_data: dict):
        """UI로부터 스케줄 데이터가 업데이트되면 호출됩니다."""
        self.schedules = schedules_data
        self._save_schedules_to_file()
        self.schedule_status_updated.emit("예약이 업데이트 및 저장되었습니다.")

    def _check_schedules(self):
        """1초마다 호출되어 현재 시간에 실행해야 할 작업이 있는지 확인합니다."""
        now = datetime.now()
        current_minute = now.minute
        
        if current_minute == self.last_checked_minute:
            return
        self.last_checked_minute = current_minute
        
        current_time_str = now.strftime("%H:%M")
        
        weekdays_map = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        current_weekday = weekdays_map[now.weekday()]
        current_date_str = now.strftime("%Y-%m-%d")

        jobs_to_run = []
        
        # 1. 요일별 스케줄 확인
        if self.schedules.get("weekly", {}).get(current_weekday):
            for job in self.schedules["weekly"][current_weekday]:
                # job['time'] is now a QTime object
                if job.get("time").toString("HH:mm") == current_time_str:
                    jobs_to_run.append(job)
                    
        # 2. 오늘 스케줄 확인 (요일별 스케줄보다 우선)
        if self.schedules.get("daily", {}).get(current_date_str):
            daily_jobs_to_run = []
            for job in self.schedules["daily"][current_date_str]:
                 if job.get("time").toString("HH:mm") == current_time_str:
                    daily_jobs_to_run.append(job)
            
            if daily_jobs_to_run:
                jobs_to_run = [j for j in jobs_to_run if j.get("time").toString("HH:mm") != current_time_str]
                jobs_to_run.extend(daily_jobs_to_run)
        
        if jobs_to_run:
            print(f"Executing {len(jobs_to_run)} jobs for {current_time_str}")
            for job in jobs_to_run:
                self._execute_job(job)

    def _execute_job(self, job: dict):
        target = job.get("target")
        action = job.get("action")
        is_on = (action == "켜기 (ON)")

        print(f"  - Job: {target} -> {action}")
        self.schedule_status_updated.emit(f"실행: {job.get('name', '이름없는 예약')}")

        if target == "전체 LED":
            mode = "Auto" if is_on else "Off"
            self.send_command('led', {'mode': mode})
        elif target == "양액 펌프":
            self.send_command('pump', {'on': is_on})
        elif target == "UV 필터":
            self.send_command('uv', {'on': is_on})
        else:
            print(f"    - Unknown job target: {target}")

    def _save_schedules_to_file(self):
        """현재 스케줄을 JSON 파일에 저장합니다. QTime 객체를 문자열로 변환합니다."""
        schedules_to_save = copy.deepcopy(self.schedules)
        for category in schedules_to_save.values():
            for day_list in category.values():
                for job in day_list:
                    if isinstance(job.get("time"), QTime):
                        job["time"] = job["time"].toString("HH:mm")
        try:
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(schedules_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"Error saving schedules: {e}")

    def _load_schedules_from_file(self):
        """JSON 파일에서 스케줄을 불러옵니다. 시간 문자열을 QTime 객체로 변환합니다."""
        if not os.path.exists(self.schedule_file):
            print("Schedule file not found. Starting with empty schedules.")
            self.schedules = {
                "weekly": {day: [] for day in ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]},
                "daily": {}
            }
        else:
            try:
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    loaded_schedules = json.load(f)
                
                for category in loaded_schedules.values():
                    for day_list in category.values():
                        for job in day_list:
                            if isinstance(job.get("time"), str):
                                job["time"] = QTime.fromString(job["time"], "HH:mm")
                
                self.schedules = loaded_schedules
                print("Schedules loaded and parsed successfully.")
            except Exception as e:
                print(f"Error loading schedules: {e}")
                self.schedules = {}
        
        # Emit signal AFTER loading and parsing
        self.schedules_loaded.emit(self.schedules)
			
