# app.py
import sys
from PyQt5 import QtWidgets
from ui.main_window import AnyGrowMainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    win = AnyGrowMainWindow()
    win.show()
    win.try_init_serial()
    win.start_timers()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
