# app.py
import sys
from datetime import datetime
from PyQt5 import QtWidgets, QtCore 
from ui.main_window import AnyGrowMainWindow
from core.app_state import AppState
from core.main_controller import MainController
from drivers.hardware import HardwareManager
from core.scheduler import Scheduler

def main():
    print("--- app.py main called ---")
    app = QtWidgets.QApplication(sys.argv)
    
    app_state = AppState()
    
    # HardwareManager와 QThread 생성 및 연결
    hw_thread = QtCore.QThread()
    hardware_manager = HardwareManager()
    hardware_manager.moveToThread(hw_thread)

    # Scheduler 생성
    scheduler = Scheduler()
    
    # MainController에 hardware_manager, hw_thread, scheduler 등을 함께 전달
    main_controller = MainController(hardware_manager, hw_thread, app_state, scheduler)
    
    # HardwareManager 스레드 시작
    hw_thread.start()
    
    win = AnyGrowMainWindow(app_state, main_controller, hardware_manager, scheduler)
    win.show()
    
    # 애플리케이션 시작 시 BMS 시간 자동 동기화 (2초 지연)
    def initial_bms_sync():
        print("[App Startup] Performing initial BMS time synchronization.")
        now = datetime.now()
        win.sync_bms_time(now)
        
    QtCore.QTimer.singleShot(2000, initial_bms_sync)

    # 애플리케이션 종료 시 스레드 정리
    app.aboutToQuit.connect(main_controller.stop_hardware) 
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
