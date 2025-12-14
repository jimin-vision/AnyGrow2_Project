# ui/widgets/control_widget.py

from PyQt5 import QtCore, QtWidgets

class ControlWidget(QtWidgets.QWidget):
    # Signals
    led_command = QtCore.pyqtSignal(str)
    brightness_command = QtCore.pyqtSignal(list)
    pump_command = QtCore.pyqtSignal(bool)
    uv_command = QtCore.pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        self._setup_led_controls()
        self._setup_brightness_controls()
        self._setup_aux_controls()

        layout.addWidget(self.gb_led)
        layout.addWidget(self.gb_bright)
        layout.addWidget(self.gb_aux)
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
        self.gb_bright = QtWidgets.QGroupBox("라인별 밝기 (0~100)")
        bright_grid = QtWidgets.QGridLayout(self.gb_bright)
        bright_grid.setHorizontalSpacing(10)
        bright_grid.setVerticalSpacing(6)

        self.brightness_controls = []
        for i in range(7):
            lbl = QtWidgets.QLabel(f"라인 {i+1}")

            slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(100)
            slider.setFixedWidth(180)

            spin = QtWidgets.QSpinBox()
            spin.setRange(0, 100)
            spin.setValue(100)
            spin.setFixedWidth(55)

            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)

            bright_grid.addWidget(lbl, i, 0)
            bright_grid.addWidget(slider, i, 1)
            bright_grid.addWidget(spin, i, 2)
            self.brightness_controls.append((slider, spin))

        btn_apply_bright = QtWidgets.QPushButton("밝기 적용")
        btn_apply_bright.clicked.connect(self._emit_brightness_command)
        bright_grid.addWidget(btn_apply_bright, 7, 0, 1, 3)

    def _emit_brightness_command(self):
        levels = [int(spin.value()) for (_slider, spin) in self.brightness_controls]
        self.brightness_command.emit(levels)

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
