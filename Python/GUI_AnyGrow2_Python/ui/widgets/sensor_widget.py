# ui/widgets/sensor_widget.py

from PyQt5 import QtCore, QtGui, QtWidgets

from ui.constants import (
    MAX_TEMP, MAX_HUM, MAX_CO2, MAX_ILLUM, get_bar_color
)


class SensorWidget(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("센서 데이터", parent)

        env_grid = QtWidgets.QGridLayout(self)
        env_grid.setHorizontalSpacing(12)
        env_grid.setVerticalSpacing(6)
        env_grid.setColumnStretch(2, 1)

        self._bars = {}  # key -> (value_label, progressbar, max_value)

        self._add_sensor_row(0, "온도", "temp", MAX_TEMP)
        self._add_sensor_row(1, "습도", "hum", MAX_HUM)
        self._add_sensor_row(2, "CO₂", "co2", MAX_CO2)
        self._add_sensor_row(3, "조도", "illum", MAX_ILLUM)

        self.lbl_last_update = QtWidgets.QLabel("마지막 갱신: -")
        self.lbl_sensor_status = QtWidgets.QLabel("센서 데이터 수신 기록 없음")
        self.lbl_sensor_status.setStyleSheet("color: blue;")

        env_grid.addWidget(self.lbl_last_update, 4, 0, 1, 3)
        env_grid.addWidget(self.lbl_sensor_status, 5, 0, 1, 3)

    def _add_sensor_row(self, r: int, title: str, key: str, max_v: float):
        name = QtWidgets.QLabel(title)
        name.setStyleSheet("font-weight: bold;")

        value_lbl = QtWidgets.QLabel("-")
        value_lbl.setMinimumWidth(95)
        value_lbl.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 1000)
        bar.setValue(0)
        bar.setTextVisible(False)
        bar.setFixedHeight(18)
        bar.setMinimumWidth(260)
        bar.setStyleSheet(
            "QProgressBar { border: 1px solid #bdbdbd; border-radius: 2px; }"
            "QProgressBar::chunk { background: #4caf50; }"
        )

        self.layout().addWidget(name, r, 0)
        self.layout().addWidget(value_lbl, r, 1)
        self.layout().addWidget(bar, r, 2)
        self._bars[key] = (value_lbl, bar, max_v)

    def update_sensor_bars(self, t: float, h: float, c: int, il: int):
        data = {
            "temp": (t, MAX_TEMP, f"{t:.1f} ℃"),
            "hum": (h, MAX_HUM, f"{h:.1f} %"),
            "co2": (float(c), MAX_CO2, f"{c} ppm"),
            "illum": (float(il), MAX_ILLUM, f"{il} lx"),
        }
        for key, (val, max_v, txt) in data.items():
            value_lbl, bar, _ = self._bars[key]

            ratio = max(0.0, min(1.0, float(val) / float(max_v)))
            bar.setValue(int(ratio * 1000))

            color = get_bar_color(key, float(val))
            value_lbl.setText(txt)
            value_lbl.setStyleSheet(f"color: {color}; font-weight: bold;")
            bar.setStyleSheet(
                "QProgressBar { border: 1px solid #bdbdbd; border-radius: 2px; }"
                f"QProgressBar::chunk {{ background: {color}; }}"
            )
    
    def set_last_update_text(self, text: str):
        self.lbl_last_update.setText(text)

    def set_sensor_status_text(self, text: str):
        self.lbl_sensor_status.setText(text)
        
    def reset(self):
        self.set_last_update_text("마지막 갱신: -")
        self.set_sensor_status_text("센서 데이터 수신 기록 없음")
        for key, (value_lbl, bar, max_v) in self._bars.items():
            value_lbl.setText("-")
            value_lbl.setStyleSheet("")
            bar.setValue(0)
            bar.setStyleSheet(
                "QProgressBar { border: 1px solid #bdbdbd; border-radius: 2px; }"
                "QProgressBar::chunk { background: #4caf50; }"
            )
