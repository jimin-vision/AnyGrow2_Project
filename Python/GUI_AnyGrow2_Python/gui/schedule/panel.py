# gui/schedule/panel.py
# 조명 스케줄 패널 전체 UI 구성

import tkinter as tk
from tkinter import ttk

from .. import state
from . import table, preset_ai


def build_schedule_panel(parent):
    """
    스케줄 전체 패널:
      - 스케줄 사용 체크 / 상태 텍스트
      - 작물 이름 입력 + 프리셋 버튼 3개
      - 스케줄 표(구간/시작/종료/모드)
      - +구간 추가 / -구간 제거 / 표 내용으로 스케줄 적용 버튼
    """
    schedule_frame = tk.LabelFrame(
        parent, text="조명 스케줄 (작물 이름 + 프리셋)", padx=10, pady=10
    )
    schedule_frame.pack(fill="x", pady=(5, 5))
    state.schedule_frame = schedule_frame

    # 상단: 스케줄 사용 체크 / 상태
    tk.Checkbutton(
        schedule_frame,
        text="스케줄 사용",
        variable=state.schedule_enabled_var,
    ).grid(row=0, column=0, sticky="w")

    tk.Label(schedule_frame, textvariable=state.schedule_status_var).grid(
        row=0, column=1, columnspan=4, sticky="w", padx=(10, 0)
    )

    # 작물 이름 입력 + 프리셋 버튼
    crop_row = tk.Frame(schedule_frame)
    crop_row.grid(row=1, column=0, columnspan=5, sticky="we", pady=(5, 10))

    tk.Label(crop_row, text="작물 이름:").pack(side="left")
    tk.Entry(
        crop_row,
        textvariable=state.crop_name_var,
        width=20,
        font=("Malgun Gothic", 10),
    ).pack(side="left", padx=(5, 10))

    ttk.Button(
        crop_row,
        text="묘목 모드",
        command=lambda: preset_ai.apply_ai_preset("seedling"),
    ).pack(side="left", padx=(0, 5))

    ttk.Button(
        crop_row,
        text="생육 모드",
        command=lambda: preset_ai.apply_ai_preset("vegetative"),
    ).pack(side="left", padx=(0, 5))

    ttk.Button(
        crop_row,
        text="개화/열매 모드",
        command=lambda: preset_ai.apply_ai_preset("flowering"),
    ).pack(side="left", padx=(0, 5))

    # 시간 형식 안내 + 헤더
    tk.Label(
        schedule_frame,
        text="(시간 형식: HH:MM, 24시간제)",
    ).grid(row=2, column=0, columnspan=5, sticky="w", pady=(0, 5))

    tk.Label(schedule_frame, text="구간").grid(row=3, column=0, sticky="w")
    tk.Label(schedule_frame, text="시작").grid(row=3, column=1, sticky="w")
    tk.Label(schedule_frame, text="종료").grid(row=3, column=2, sticky="w")
    tk.Label(schedule_frame, text="모드").grid(row=3, column=3, sticky="w")

    # 기본 3줄 생성
    for _ in range(3):
        table.add_schedule_row()

    last_row = 4 + len(state.schedule_rows) + 1

    # 하단 버튼들
    state.apply_btn = tk.Button(
        schedule_frame,
        text="표 내용으로 스케줄 적용",
        command=table.apply_manual_schedule,
    )
    state.apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")

    state.add_btn = tk.Button(
        schedule_frame,
        text="+ 구간 추가",
        command=table.add_schedule_row,
    )
    state.add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")

    state.del_btn = tk.Button(
        schedule_frame,
        text="- 구간 제거",
        command=table.remove_schedule_row,
    )
    state.del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")
