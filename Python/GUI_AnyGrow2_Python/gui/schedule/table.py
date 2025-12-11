# gui/schedule/table.py
# 스케줄 표(행 추가/삭제/적용) 관련 로직

import tkinter as tk
from tkinter import ttk, messagebox

from .. import state
import schedule_core as sched_core
import hardware as hw


def _set_focus_row(idx: int):
    state.current_focus_row_index = idx


def add_schedule_row():
    """스케줄 표에 한 줄 추가."""
    idx = len(state.schedule_rows)
    row = 4 + idx  # 헤더 4줄 이후부터 본문

    start_var = tk.StringVar()
    end_var = tk.StringVar()
    mode_var = tk.StringVar(value="On")

    lbl = tk.Label(state.schedule_frame, text=str(idx + 1), width=3, anchor="w")
    e_start = tk.Entry(state.schedule_frame, textvariable=start_var, width=6)
    e_end = tk.Entry(state.schedule_frame, textvariable=end_var, width=6)
    opt = ttk.Combobox(
        state.schedule_frame,
        textvariable=mode_var,
        values=("On", "Mood", "Off"),
        state="readonly",
        width=8,
    )

    lbl.grid(row=row, column=0, sticky="w")
    e_start.grid(row=row, column=1, sticky="w")
    e_end.grid(row=row, column=2, sticky="w")
    opt.grid(row=row, column=3, sticky="w")

    def _make_focus_handler(i):
        return lambda event: _set_focus_row(i)

    e_start.bind("<FocusIn>", _make_focus_handler(idx))
    e_end.bind("<FocusIn>", _make_focus_handler(idx))
    opt.bind("<FocusIn>", _make_focus_handler(idx))

    state.schedule_rows.append((lbl, e_start, e_end, opt))
    state.manual_start_vars.append(start_var)
    state.manual_end_vars.append(end_var)
    state.manual_mode_vars.append(mode_var)

    # 버튼 위치 재배치
    last_row = 4 + len(state.schedule_rows) + 1
    if state.apply_btn is not None:
        state.apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")
    if state.add_btn is not None:
        state.add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")
    if state.del_btn is not None:
        state.del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")


def remove_schedule_row():
    """마지막 행 제거 (최소 3줄은 남김)."""
    if len(state.schedule_rows) <= 3:
        return

    lbl, e_start, e_end, opt = state.schedule_rows.pop()
    lbl.destroy()
    e_start.destroy()
    e_end.destroy()
    opt.destroy()

    state.manual_start_vars.pop()
    state.manual_end_vars.pop()
    state.manual_mode_vars.pop()

    # 행 번호 다시 정리
    for i, (lbl, *_rest) in enumerate(state.schedule_rows):
        lbl.config(text=str(i + 1))

    # 포커스 인덱스 보정
    if state.current_focus_row_index >= len(state.schedule_rows):
        state.current_focus_row_index = len(state.schedule_rows) - 1

    # 버튼 위치 재배치
    last_row = 4 + len(state.schedule_rows) + 1
    if state.apply_btn is not None:
        state.apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")
    if state.add_btn is not None:
        state.add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")
    if state.del_btn is not None:
        state.del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")


def apply_manual_schedule():
    """표에 입력된 내용 → 스케줄 적용 + 현재 모드 즉시 반영."""
    entries = []
    for i in range(len(state.manual_start_vars)):
        s_txt = state.manual_start_vars[i].get().strip()
        e_txt = state.manual_end_vars[i].get().strip()
        mode = state.manual_mode_vars[i].get()
        if s_txt == "" or e_txt == "":
            continue
        entries.append({"start": s_txt, "end": e_txt, "mode": mode})

    try:
        sched_core.set_schedule(entries)
    except ValueError as e:
        messagebox.showerror("시간 형식 오류", str(e))
        return

    state.schedule_status_var.set(f"스케줄 {len(entries)}개 구간 적용됨")
    state.schedule_enabled_var.set(True)
    apply_schedule_now()


def apply_schedule_now():
    """현재 시간 기준 모드 즉시 적용."""
    mode = sched_core.get_mode_for_now()
    if mode is None:
        state.schedule_status_var.set("스케줄 없음")
        return

    try:
        hw.send_led_packet(mode)
        state.schedule_status_var.set(f"현재 시간 기준 모드 적용: {mode}")
    except Exception as e:
        state.schedule_status_var.set(f"[ERROR] 스케줄 적용 실패: {e}")
        messagebox.showerror("Schedule Error", str(e))
