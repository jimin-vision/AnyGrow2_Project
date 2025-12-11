# gui/helpers.py
# 센서 막대 그래프 그리기 및 색상 계산 등 공통 GUI 헬퍼 함수

import tkinter as tk
from . import state

BAR_WIDTH = 200
BAR_HEIGHT = 18

MAX_TEMP = 40.0
MAX_HUM = 100.0
MAX_CO2 = 2000.0
MAX_ILLUM = 5000.0  # 막대 그래프 스케일용


def create_bar(parent, row, label_text, var, key):
    """
    센서 막대 그래프 1줄 생성 및 state.bar_widgets 에 등록.
      key: "temp" / "hum" / "co2" / "illum"
    """
    tk.Label(parent, text=label_text, width=8, anchor="w").grid(
        row=row, column=0, sticky="w"
    )
    value_label = tk.Label(parent, textvariable=var, width=12, anchor="w")
    value_label.grid(row=row, column=1, sticky="w")

    canvas = tk.Canvas(parent, width=BAR_WIDTH, height=BAR_HEIGHT, highlightthickness=1)
    canvas.grid(row=row, column=2, sticky="w", padx=(10, 0))
    rect = canvas.create_rectangle(0, 0, 0, BAR_HEIGHT, fill="#4caf50")

    state.bar_widgets[key] = (canvas, rect, value_label)
    return canvas, rect, value_label


def get_bar_color(sensor, value):
    """센서 종류/값에 따라 막대 색상 반환."""
    if sensor == "temp":
        if value < 15 or value > 30:
            return "#f44336"
        elif 15 <= value <= 18 or 27 <= value <= 30:
            return "#ff9800"
        else:
            return "#4caf50"
    if sensor == "hum":
        if value < 30 or value > 80:
            return "#f44336"
        elif 30 <= value <= 40 or 70 <= value <= 80:
            return "#ff9800"
        else:
            return "#4caf50"
    if sensor == "co2":
        if value > 1500:
            return "#f44336"
        elif value > 1000:
            return "#ff9800"
        else:
            return "#4caf50"
    if sensor == "illum":
        if value < 200:
            return "#f44336"
        elif value < 800:
            return "#ff9800"
        else:
            return "#4caf50"
    return "#4caf50"


def update_sensor_bars(t, h, c, il):
    """4개 센서 막대 그래프를 한 번에 업데이트."""
    values = {
        "temp": (t, MAX_TEMP),
        "hum": (h, MAX_HUM),
        "co2": (c, MAX_CO2),
        "illum": (il, MAX_ILLUM),
    }
    for name, (value, max_val) in values.items():
        canvas, rect, label = state.bar_widgets[name]
        ratio = max(0.0, min(1.0, float(value) / float(max_val)))
        width = int(ratio * BAR_WIDTH)
        color = get_bar_color(name, value)
        canvas.coords(rect, 0, 0, width, BAR_HEIGHT)
        canvas.itemconfig(rect, fill=color)
        label.config(fg=color)
