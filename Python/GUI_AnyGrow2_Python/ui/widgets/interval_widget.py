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

        # Time Inputs using QSpinBox
        current_time = QtCore.QTime.currentTime()
        
        self.spin_start_hour = QtWidgets.QSpinBox()
        self.spin_start_hour.setRange(0, 23)
        self.spin_start_hour.setValue(current_time.hour())
        self.spin_start_hour.setFixedWidth(60)
        self.spin_start_hour.setAlignment(QtCore.Qt.AlignRight)
        
        self.spin_start_min = QtWidgets.QSpinBox()
        self.spin_start_min.setRange(0, 59)
        self.spin_start_min.setValue(current_time.minute())
        self.spin_start_min.setFixedWidth(60)
        self.spin_start_min.setAlignment(QtCore.Qt.AlignRight)

        self.spin_end_hour = QtWidgets.QSpinBox()
        self.spin_end_hour.setRange(0, 23)
        self.spin_end_hour.setValue(current_time.hour())
        self.spin_end_hour.setFixedWidth(60)
        self.spin_end_hour.setAlignment(QtCore.Qt.AlignRight)

        self.spin_end_min = QtWidgets.QSpinBox()
        self.spin_end_min.setRange(0, 59)
        self.spin_end_min.setValue(current_time.minute())
        self.spin_end_min.setFixedWidth(60)
        self.spin_end_min.setAlignment(QtCore.Qt.AlignRight)

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
        layout.addStretch(1) 
        layout.addWidget(self.spin_start_hour)
        layout.addWidget(QtWidgets.QLabel(":"))
        layout.addWidget(self.spin_start_min)
        layout.addWidget(QtWidgets.QLabel("~"))
        layout.addWidget(self.spin_end_hour)
        layout.addWidget(QtWidgets.QLabel(":"))
        layout.addWidget(self.spin_end_min)
        layout.addWidget(self.cmb_target)
        layout.addWidget(self.cmb_action)
        layout.addWidget(btn_set_now)
        layout.addWidget(self.btn_remove)

    def get_values(self):
        """Returns the current settings of the widget."""
        start_time = QtCore.QTime(self.spin_start_hour.value(), self.spin_start_min.value())
        end_time = QtCore.QTime(self.spin_end_hour.value(), self.spin_end_min.value())
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
        self.spin_start_hour.setValue(current_time.hour())
        self.spin_start_min.setValue(current_time.minute())
