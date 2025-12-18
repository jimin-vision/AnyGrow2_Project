# core/scheduler.py
import json
import os
import copy
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QTime, QTimer

from core.constants import WEEKDAYS_MAP, SCHEDULE_FILE

class Scheduler(QObject):
    """
    예약 로딩, 저장, 확인을 처리합니다.
    타이머를 실행하여 현재 시간에 실행할 작업이 있는지 확인합니다.
    """
    job_to_execute = pyqtSignal(dict)
    schedule_status_updated = pyqtSignal(str)
    schedules_loaded = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.schedules = {}
        self._load_schedules_from_file()

        self.last_checked_minute = -1
        self.scheduler_timer = QTimer(self)
        self.scheduler_timer.timeout.connect(self.check_schedules)
        self.scheduler_timer.start(1000)  # 1초마다 확인

    def update_schedules(self, schedules_data: dict):
        """
        UI에서 예약 데이터가 업데이트될 때 호출됩니다.
        """
        self.schedules = schedules_data
        self._save_schedules_to_file()
        self.schedule_status_updated.emit("예약이 업데이트 및 저장되었습니다.")

    def check_schedules(self):
        """
        현재 시간에 실행할 작업이 있는지 확인합니다.
        이 메서드는 scheduler_timer에 의해 1초마다 호출됩니다.
        """
        if self.schedules.get('disabled', False):
            return
            
        now = datetime.now()
        current_minute = now.minute
        
        # 같은 분에 여러 번 확인하는 것을 방지합니다.
        if current_minute == self.last_checked_minute:
            return
        self.last_checked_minute = current_minute
        
        current_time_str = now.strftime("%H:%M")
        current_weekday = WEEKDAYS_MAP[now.weekday()]
        current_date_str = now.strftime("%Y-%m-%d")

        jobs_to_run = []
        
        # "오늘" 예약이 주간 예약보다 우선순위가 높습니다.
        daily_jobs = self.schedules.get("daily", {}).get(current_date_str)
        if daily_jobs:
            for job in daily_jobs:
                if job.get("time").toString("HH:mm") == current_time_str:
                    jobs_to_run.append(job)
        # "오늘" 예약이 없으면 주간 예약을 확인합니다.
        else:
            weekly_jobs = self.schedules.get("weekly", {}).get(current_weekday)
            if weekly_jobs:
                for job in weekly_jobs:
                    if job.get("time").toString("HH:mm") == current_time_str:
                        jobs_to_run.append(job)
        
        if jobs_to_run:
            print(f"실행할 작업 {len(jobs_to_run)}개 ({current_time_str})")
            for job in jobs_to_run:
                self.job_to_execute.emit(job)

    def _save_schedules_to_file(self):
        """
        현재 예약을 JSON 파일에 저장합니다.
        직렬화를 위해 QTime 객체를 문자열로 변환합니다.
        """
        schedules_to_save = copy.deepcopy(self.schedules)
        for category_key in ['weekly', 'daily', 'templates']:
            category = schedules_to_save.get(category_key, {})
            if not isinstance(category, dict): continue
            for day_list in category.values():
                if isinstance(day_list, list):
                    for job in day_list:
                        if isinstance(job.get("time"), QTime):
                            job["time"] = job["time"].toString("HH:mm")
        try:
            with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
                json.dump(schedules_to_save, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"예약 저장 오류: {e}")

    def _load_schedules_from_file(self):
        """
        JSON 파일에서 예약을 불러옵니다.
        시간 문자열을 QTime 객체로 변환합니다.
        """
        if not os.path.exists(SCHEDULE_FILE):
            print("예약 파일을 찾을 수 없습니다. 빈 예약으로 시작합니다.")
            self.schedules = {
                "weekly": {day: [] for day in WEEKDAYS_MAP},
                "daily": {},
                "templates": {}
            }
        else:
            try:
                with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
                    loaded_schedules = json.load(f)
                
                for category_key in ['weekly', 'daily', 'templates']:
                    category = loaded_schedules.get(category_key, {})
                    if not isinstance(category, dict): continue
                    for day_list in category.values():
                        if isinstance(day_list, list):
                            for job in day_list:
                                if isinstance(job.get("time"), str):
                                    job["time"] = QTime.fromString(job["time"], "HH:mm")
                
                self.schedules = loaded_schedules
                print("예약을 성공적으로 불러왔습니다.")
            except Exception as e:
                print(f"예약 불러오기 오류: {e}")
                self.schedules = {}
        
        # 로딩 및 파싱 후 시그널 발생
        self.schedules_loaded.emit(self.schedules)
