# ui/widgets/interval_widget.py
from PyQt5 import QtCore, QtWidgets, QtGui

class IntervalWidget(QtWidgets.QFrame):
    
    remove_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        self.lbl_num = QtWidgets.QLabel("구간1")
        font = self.lbl_num.font()
        font.setBold(True)
        self.lbl_num.setFont(font)

        # Time Inputs using QLineEdit with Validators
        current_time = QtCore.QTime.currentTime()
        
        self.le_start_hour = QtWidgets.QLineEdit(str(current_time.hour()))
        self.le_start_hour.setValidator(QtGui.QIntValidator(0, 23, self))
        self.le_start_hour.setFixedWidth(40)
        self.le_start_hour.setAlignment(QtCore.Qt.AlignRight)
        self.le_start_hour.setPlaceholderText("Hour")
        
        self.le_start_min = QtWidgets.QLineEdit(str(current_time.minute()))
        self.le_start_min.setValidator(QtGui.QIntValidator(0, 59, self))
        self.le_start_min.setFixedWidth(40)
        self.le_start_min.setAlignment(QtCore.Qt.AlignRight)
        self.le_start_min.setPlaceholderText("Min")

        self.le_end_hour = QtWidgets.QLineEdit(str(current_time.hour()))
        self.le_end_hour.setValidator(QtGui.QIntValidator(0, 23, self))
        self.le_end_hour.setFixedWidth(40)
        self.le_end_hour.setAlignment(QtCore.Qt.AlignRight)
        self.le_end_hour.setPlaceholderText("Hour")

        self.le_end_min = QtWidgets.QLineEdit(str(current_time.minute()))
        self.le_end_min.setValidator(QtGui.QIntValidator(0, 59, self))
        self.le_end_min.setFixedWidth(40)
        self.le_end_min.setAlignment(QtCore.Qt.AlignRight)
        self.le_end_min.setPlaceholderText("Min")

        # ComboBoxes
        self.cmb_action = QtWidgets.QComboBox()
        self.cmb_action.addItems(["켜기 (ON)", "끄기 (OFF)"])
        self.cmb_target = QtWidgets.QComboBox()
        self.cmb_target.addItems(["전체 LED", "양액 펌프", "UV 필터"])
        
        # Buttons
        btn_set_now = QtWidgets.QPushButton("현재시간")
        btn_set_now.clicked.connect(self._set_start_time_now)
        self.btn_remove = QtWidgets.QPushButton("제거")
        self.btn_remove.setStyleSheet("color: red;")
        self.btn_remove.clicked.connect(self.remove_requested.emit)

        # Add widgets to layout
        layout.addWidget(self.lbl_num)
        layout.addStretch(1) # This is the key change
        layout.addWidget(self.le_start_hour)
        layout.addWidget(QtWidgets.QLabel(":"))
        layout.addWidget(self.le_start_min)
        layout.addWidget(QtWidgets.QLabel("~"))
        layout.addWidget(self.le_end_hour)
        layout.addWidget(QtWidgets.QLabel(":"))
        layout.addWidget(self.le_end_min)
        layout.addWidget(self.cmb_target)
        layout.addWidget(self.cmb_action)
        layout.addWidget(btn_set_now)
        layout.addWidget(self.btn_remove)

    def get_values(self):
        """Returns the current settings of the widget."""
        try:
            start_hour = int(self.le_start_hour.text())
            start_min = int(self.le_start_min.text())
            end_hour = int(self.le_end_hour.text())
            end_min = int(self.le_end_min.text())
        except (ValueError, TypeError):
            # Return null QTime if text is not a valid int
            return { 
                "start_time": QtCore.QTime(), "end_time": QtCore.QTime(),
                "action": "", "target": ""
            }

        start_time = QtCore.QTime(start_hour, start_min)
        end_time = QtCore.QTime(end_hour, end_min)
        return {
            "start_time": start_time,
            "end_time": end_time,
            "action": self.cmb_action.currentText(),
            "target": self.cmb_target.currentText()
        }

    def set_number(self, num: int):
        self.lbl_num.setText(f"구간{num}")

    def _set_start_time_now(self):
        current_time = QtCore.QTime.currentTime()
        self.le_start_hour.setText(str(current_time.hour()))
        self.le_start_min.setText(str(current_time.minute()))
