# ui/widgets/control_widget.py

from PyQt5 import QtCore, QtWidgets

class ControlWidget(QtWidgets.QWidget):
    # Signals
    led_command = QtCore.pyqtSignal(str)
    channel_led_command = QtCore.pyqtSignal(list)
    pump_command = QtCore.pyqtSignal(bool)
    uv_command = QtCore.pyqtSignal(bool)
    timer_command = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self._setup_led_controls()
        self._setup_brightness_controls()
        self._setup_aux_controls()
        self._setup_timer_controls()

        layout.addWidget(self.gb_led)
        layout.addWidget(self.gb_bright)
        layout.addWidget(self.gb_aux)
        layout.addWidget(self.gb_timer)
        layout.addStretch(1)

    def _setup_led_controls(self):
        self.gb_led = QtWidgets.QGroupBox("LED 제어 (전체)")
        led_grid = QtWidgets.QGridLayout(self.gb_led)

        btn_off = QtWidgets.QPushButton("LED Off")
        btn_mood = QtWidgets.QPushButton("LED Mood")
        btn_on = QtWidgets.QPushButton("LED On")

        btn_off.clicked.connect(lambda: self.led_command.emit("Off"))
        btn_mood.clicked.connect(lambda: self.led_command.emit("Mood"))
        btn_on.clicked.connect(lambda: self.led_command.emit("On"))

        btn_off.setMinimumWidth(90)
        btn_mood.setMinimumWidth(90)
        btn_on.setMinimumWidth(90)

        led_grid.addWidget(btn_off, 0, 0)
        led_grid.addWidget(btn_mood, 0, 1)
        led_grid.addWidget(btn_on, 0, 2)

    def _setup_brightness_controls(self):
        self.gb_bright = QtWidgets.QGroupBox("채널별 LED 제어")
        bright_grid = QtWidgets.QGridLayout(self.gb_bright)
        bright_grid.setHorizontalSpacing(10)
        bright_grid.setVerticalSpacing(6)

        self.brightness_controls = []
        for i in range(4):
            # Channel On/Off Checkbox
            chk_on = QtWidgets.QCheckBox(f"채널 {i+1}")
            chk_on.setChecked(True)

            # Frequency (Hz)
            lbl_hz = QtWidgets.QLabel("주파수 (Hz):")
            spin_hz = QtWidgets.QSpinBox()
            spin_hz.setRange(1, 1000)
            spin_hz.setValue(1) # Set initial value to 1
            spin_hz.setFixedWidth(60)
            spin_hz.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons) # Remove arrow buttons

            # Brightness
            lbl_bright = QtWidgets.QLabel("밝기:")
            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(100)
            slider.setFixedWidth(120)

            spin_bright = QtWidgets.QSpinBox()
            spin_bright.setRange(0, 100)
            spin_bright.setValue(100)
            spin_bright.setFixedWidth(55)

            slider.valueChanged.connect(spin_bright.setValue)
            spin_bright.valueChanged.connect(slider.setValue)

            # Layout
            bright_grid.addWidget(chk_on, i, 0)
            bright_grid.addWidget(lbl_hz, i, 1)
            bright_grid.addWidget(spin_hz, i, 2)
            bright_grid.addWidget(lbl_bright, i, 3)
            bright_grid.addWidget(slider, i, 4)
            bright_grid.addWidget(spin_bright, i, 5)
            
            self.brightness_controls.append((chk_on, spin_hz, slider, spin_bright))

        btn_apply_bright = QtWidgets.QPushButton("채널별 LED 설정 저장")
        btn_apply_bright.clicked.connect(self._emit_channel_led_command)
        bright_grid.addWidget(btn_apply_bright, 4, 0, 1, 6)

    def _emit_channel_led_command(self):
        settings = []
        for chk_on, spin_hz, _slider, spin_bright in self.brightness_controls:
            settings.append({
                'on': chk_on.isChecked(),
                'hz': spin_hz.value(),
                'brightness': spin_bright.value()
            })
        self.channel_led_command.emit(settings)

    def _setup_aux_controls(self):
        self.gb_aux = QtWidgets.QGroupBox("보조 장치 제어")
        aux_grid = QtWidgets.QGridLayout(self.gb_aux)
        aux_grid.setHorizontalSpacing(10)
        aux_grid.setVerticalSpacing(8)

        aux_grid.addWidget(QtWidgets.QLabel("양액 펌프"), 0, 0)
        btn_pump_on = QtWidgets.QPushButton("ON")
        btn_pump_off = QtWidgets.QPushButton("OFF")
        btn_pump_on.clicked.connect(lambda: self.pump_command.emit(True))
        btn_pump_off.clicked.connect(lambda: self.pump_command.emit(False))
        aux_grid.addWidget(btn_pump_on, 0, 1)
        aux_grid.addWidget(btn_pump_off, 0, 2)

        aux_grid.addWidget(QtWidgets.QLabel("UV 필터"), 1, 0)
        btn_uv_on = QtWidgets.QPushButton("ON")
        btn_uv_off = QtWidgets.QPushButton("OFF")
        btn_uv_on.clicked.connect(lambda: self.uv_command.emit(True))
        btn_uv_off.clicked.connect(lambda: self.uv_command.emit(False))
        aux_grid.addWidget(btn_uv_on, 1, 1)
        aux_grid.addWidget(btn_uv_off, 1, 2)
        
    def _setup_timer_controls(self):
        self.gb_timer = QtWidgets.QGroupBox("타이머 제어")
        timer_grid = QtWidgets.QGridLayout(self.gb_timer)
        
        # Start time
        timer_grid.addWidget(QtWidgets.QLabel("시작 시간:"), 0, 0)
        self.time_edit_start = QtWidgets.QTimeEdit()
        self.time_edit_start.setDisplayFormat("HH:mm")
        self.time_edit_start.setTime(QtCore.QTime.currentTime())
        timer_grid.addWidget(self.time_edit_start, 0, 1)
        
        # End time
        timer_grid.addWidget(QtWidgets.QLabel("종료 시간:"), 1, 0)
        self.time_edit_end = QtWidgets.QTimeEdit()
        self.time_edit_end.setDisplayFormat("HH:mm")
        self.time_edit_end.setTime(QtCore.QTime.currentTime().addSecs(3600)) # Default to 1 hour later
        timer_grid.addWidget(self.time_edit_end, 1, 1)
        
        # Target device
        timer_grid.addWidget(QtWidgets.QLabel("제어 대상:"), 2, 0)
        self.cmb_timer_target = QtWidgets.QComboBox()
        self.cmb_timer_target.addItems(["전체 LED", "양액 펌프", "UV 필터"])
        timer_grid.addWidget(self.cmb_timer_target, 2, 1)

        # Start button
        btn_start_timer = QtWidgets.QPushButton("타이머 시작")
        btn_start_timer.clicked.connect(self._emit_timer_command)
        timer_grid.addWidget(btn_start_timer, 3, 0, 1, 2)

    def _emit_timer_command(self):
        settings = {
            'target': self.cmb_timer_target.currentText(),
            'start_time': self.time_edit_start.time(),
            'end_time': self.time_edit_end.time()
        }
        self.timer_command.emit(settings)
