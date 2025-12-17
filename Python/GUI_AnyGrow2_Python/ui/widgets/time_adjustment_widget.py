from PyQt5 import QtWidgets, QtCore, QtGui
from datetime import datetime

class TimeAdjustmentWidget(QtWidgets.QWidget):
    time_applied = QtCore.pyqtSignal(datetime) # Signal to emit when time is applied

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.btn_edit_time = QtWidgets.QPushButton("시간 수정")
        self.btn_apply_time = QtWidgets.QPushButton("BMS 적용") # Changed text


        layout.addWidget(self.btn_edit_time)
        layout.addWidget(self.btn_apply_time)

        self.btn_edit_time.clicked.connect(self._show_time_setting_dialog)
        self.btn_apply_time.clicked.connect(self._on_apply_current_system_time)

    def _show_time_setting_dialog(self):
        dialog = TimeSettingDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            selected_time = dialog.get_selected_time()
            if selected_time:
                # Emit signal to main window or controller to handle time update
                self.time_applied.emit(selected_time)
            
    def _on_apply_current_system_time(self):
        # Emit signal to main window or controller to handle current system time update
        self.time_applied.emit(datetime.now())


class TimeSettingDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("시간 설정")
        self.setFixedSize(250, 150)
        self._setup_ui()
        self._selected_time = None

    def _setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Hour and Minute input
        time_input_layout = QtWidgets.QHBoxLayout()
        self.spinbox_hour = QtWidgets.QSpinBox()
        self.spinbox_hour.setRange(0, 23)
        self.spinbox_hour.setSuffix(" 시")
        self.spinbox_hour.setValue(datetime.now().hour)
        self.spinbox_minute = QtWidgets.QSpinBox()
        self.spinbox_minute.setRange(0, 59)
        self.spinbox_minute.setSuffix(" 분")
        self.spinbox_minute.setValue(datetime.now().minute)

        time_input_layout.addWidget(self.spinbox_hour)
        time_input_layout.addWidget(self.spinbox_minute)
        layout.addLayout(time_input_layout)

        # "현재 시간" button
        btn_current_time = QtWidgets.QPushButton("현재 시간")
        btn_current_time.clicked.connect(self._set_current_time)
        layout.addWidget(btn_current_time)

        # Apply/Cancel buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _set_current_time(self):
        now = datetime.now()
        self.spinbox_hour.setValue(now.hour)
        self.spinbox_minute.setValue(now.minute)

    def accept(self):
        hour = self.spinbox_hour.value()
        minute = self.spinbox_minute.value()
        current_second = datetime.now().second # Get current second
        # Set a dummy date, only hour and minute are relevant
        self._selected_time = datetime(2000, 1, 1, hour, minute, current_second)
        super().accept()

    def get_selected_time(self):
        return self._selected_time
