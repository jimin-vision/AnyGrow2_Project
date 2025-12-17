# ui/widgets/control_widget.py
from PyQt5 import QtCore, QtWidgets, QtGui
from datetime import datetime
from .analog_clock_widget import AnalogClockWidget
from .time_adjustment_widget import TimeAdjustmentWidget

class ControlWidget(QtWidgets.QWidget):
    # Signals
    led_command = QtCore.pyqtSignal(str)
    channel_led_command = QtCore.pyqtSignal(list)
    pump_command = QtCore.pyqtSignal(bool)
    uv_command = QtCore.pyqtSignal(bool)
    bms_time_sync_command = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.bms_time = QtCore.QTime.currentTime()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self._setup_led_controls()
        self._setup_brightness_controls()
        self._setup_aux_controls()
        self._setup_bms_controls()

        layout.addWidget(self.gb_led)
        layout.addWidget(self.gb_bright)
        layout.addWidget(self.gb_aux)
        layout.addWidget(self.gb_bms)
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
            chk_on = QtWidgets.QCheckBox(f"채널 {i+1}")
            chk_on.setChecked(True)
            lbl_hz = QtWidgets.QLabel("주파수 (Hz):")
            spin_hz = QtWidgets.QSpinBox()
            spin_hz.setRange(1, 1000)
            spin_hz.setValue(1)
            spin_hz.setFixedWidth(60)
            spin_hz.setButtonSymbols(QtWidgets.QAbstractSpinBox.NoButtons)
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
        
    def _setup_bms_controls(self):
        self.gb_bms = QtWidgets.QGroupBox("BMS 시간 설정")
        bms_layout = QtWidgets.QVBoxLayout(self.gb_bms)

        time_display_layout = QtWidgets.QHBoxLayout()
        self.bms_analog_clock = AnalogClockWidget()
        self.bms_analog_clock.setFixedSize(120, 120) # Increased size further
        self.bms_analog_clock.setStyle(2) # Style 2 as requested

        self.lbl_bms_current_time = QtWidgets.QLabel("HH시 MM분")
        font = self.lbl_bms_current_time.font()
        font.setPointSize(20) # Increased font size further
        font.setBold(True)
        self.lbl_bms_current_time.setFont(font)
        self.lbl_bms_current_time.setAlignment(QtCore.Qt.AlignCenter)

        time_display_layout.addStretch(1) # Center align the elements
        time_display_layout.addWidget(self.bms_analog_clock)
        time_display_layout.addStretch(1) # Add spacing between clock and digital time
        time_display_layout.addWidget(self.lbl_bms_current_time)
        time_display_layout.addStretch(1) # Center align the elements

        # Add spacing above the time adjustment widget
        bms_layout.addSpacing(20) # Increased spacing (e.g., 20 pixels)
        self.bms_time_adjustment_widget = TimeAdjustmentWidget()
        # Connect the time_applied signal from TimeAdjustmentWidget to ControlWidget's bms_time_sync_command
        self.bms_time_adjustment_widget.time_applied.connect(
            lambda dt: self.bms_time_sync_command.emit({
                'hour': dt.hour,
                'minute': dt.minute,
                'second': dt.second
            })
        )

        bms_layout.addLayout(time_display_layout)
        bms_layout.addSpacing(40) # Increased spacing further (e.g., 40 pixels)
        bms_layout.addWidget(self.bms_time_adjustment_widget)

        self.bms_clock_timer = QtCore.QTimer(self)
        self.bms_clock_timer.setInterval(1000)
        self.bms_clock_timer.timeout.connect(self._update_bms_clock_display)
        self.bms_clock_timer.start()
        
    def _update_bms_clock_display(self):
        now = datetime.now()
        now_str = now.strftime("%H시 %M분")
        self.lbl_bms_current_time.setText(now_str)
        self.bms_analog_clock.setTime(QtCore.QTime(now.hour, now.minute, now.second))