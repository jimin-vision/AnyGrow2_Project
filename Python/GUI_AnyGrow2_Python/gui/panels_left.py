# gui/panels_left.py
# 왼쪽 패널: 센서 막대 그래프 + 조명 스케줄 패널 + 센서 RAW 패킷

import tkinter as tk

from . import state, helpers
from . import schedule  # gui/schedule 패키지


def build_left_panel(parent):
    """
    왼쪽 패널 전체 구성:
      - 센서 막대 그래프
      - 조명 스케줄 패널 (별도 모듈)
      - 센서 RAW 패킷 표시
    """
    # ---- 센서 막대 ----
    env_frame = tk.LabelFrame(parent, text="센서 데이터", padx=10, pady=10)
    env_frame.pack(fill="x", pady=(0, 5))

    helpers.create_bar(env_frame, 0, "온도", state.temp_var, "temp")
    helpers.create_bar(env_frame, 1, "습도", state.hum_var, "hum")
    helpers.create_bar(env_frame, 2, "CO₂", state.co2_var, "co2")
    helpers.create_bar(env_frame, 3, "조도", state.illum_var, "illum")

    tk.Label(env_frame, textvariable=state.last_update_var).grid(
        row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
    )
    tk.Label(env_frame, textvariable=state.sensor_status_var, fg="blue").grid(
        row=5, column=0, columnspan=3, sticky="w"
    )

    # ---- 조명 스케줄 패널 (별도 모듈에 위임) ----
    schedule.build_schedule_panel(parent)

    # ---- RAW 패킷 표시 ----
    sensor_frame = tk.LabelFrame(
        parent, text="센서 데이터 (수신 패킷 문자열)", padx=10, pady=10
    )
    sensor_frame.pack(fill="both", expand=True, pady=(5, 0))

    sensor_text = tk.Label(
        sensor_frame,
        textvariable=state.raw_data_var,
        anchor="nw",
        justify="left",
        wraplength=600,
    )
    sensor_text.pack(fill="both", expand=True)
