# app.py
import sys
from PyQt5 import QtWidgets, QtCore # QtCore 임포트 추가
from ui.main_window import AnyGrowMainWindow
from core.app_state import AppState
from core.main_controller import MainController
from drivers.hardware import HardwareManager

def main():
    print("--- app.py main called ---")
    app = QtWidgets.QApplication(sys.argv)
    
    app_state = AppState()
    
    # HardwareManager와 QThread 생성 및 연결
    hw_thread = QtCore.QThread()
    hardware_manager = HardwareManager()
    hardware_manager.moveToThread(hw_thread) # HardwareManager를 스레드로 이동

    # MainController에 hardware_manager와 hw_thread를 함께 전달
    main_controller = MainController(hardware_manager, hw_thread, app_state)
    
    # HardwareManager 스레드 시작
    hw_thread.start()
    
    win = AnyGrowMainWindow(app_state, main_controller, hardware_manager)
    win.show()
    
    # 애플리케이션 종료 시 스레드 정리
    app.aboutToQuit.connect(main_controller.stop_hardware) 
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
