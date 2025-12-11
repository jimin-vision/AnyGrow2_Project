# gui/panels_right.py
# 오른쪽 패널: LED 전체 제어 + 라인별 밝기 + 양액 펌프 / UV 필터

import tkinter as tk
from tkinter import messagebox

from . import state
import hardware as hw


def send_led_command(mode: str):
    """LED 전체 모드 전송."""
    try:
        hw.send_led_packet(mode)
        state.status_var.set(f"LED 명령 전송: {mode}")
    except Exception as e:
        state.status_var.set(f"[ERROR] LED 전송 실패: {e}")
        messagebox.showerror("LED Error", str(e))


def send_pump_command(on: bool):
    """양액 펌프 On/Off."""
    try:
        hw.send_pump(on)
        state.status_var.set(f"양액 펌프: {'On' if on else 'Off'} 명령 전송")
    except Exception as e:
        state.status_var.set(f"[ERROR] 양액 펌프 제어 실패: {e}")
        messagebox.showerror("Pump Error", str(e))


def send_uv_command(on: bool):
    """UV 필터 On/Off."""
    try:
        hw.send_uv(on)
        state.status_var.set(f"UV 필터: {'On' if on else 'Off'} 명령 전송")
    except Exception as e:
        state.status_var.set(f"[ERROR] UV 필터 제어 실패: {e}")
        messagebox.showerror("UV Error", str(e))


def apply_brightness_from_gui():
    """밝기 슬라이더 값들을 모아서 hardware.apply_brightness_levels 로 전달."""
    levels = []
    for line in state.brightness_lines:
        v = line["var"].get()
        try:
            iv = int(v)
        except (TypeError, ValueError):
            iv = 0
        iv = max(0, min(100, iv))
        levels.append(iv)

    try:
        hw.apply_brightness_levels(levels)
        state.status_var.set(f"[BRIGHT] 7 라인 밝기 적용 요청: {levels}")
    except Exception as e:
        state.status_var.set(f"[ERROR] 밝기 적용 실패: {e}")
        messagebox.showerror("Brightness Error", str(e))


def build_right_panel(parent):
    """
    오른쪽 패널 전체 구성:
      - LED 전체 On/Mood/Off
      - 7라인 밝기 슬라이더 + 숫자 입력
      - 양액 펌프/UV 필터 On/Off
    """
    # LED 제어
    led_frame = tk.LabelFrame(parent, text="LED 제어 (전체)", padx=10, pady=10)
    led_frame.pack(fill="x", pady=(0, 5))

    tk.Button(
        led_frame, text="LED Off", width=10,
        command=lambda: send_led_command("Off"),
    ).grid(row=0, column=0, padx=5, pady=2)

    tk.Button(
        led_frame, text="LED Mood", width=10,
        command=lambda: send_led_command("Mood"),
    ).grid(row=0, column=1, padx=5, pady=2)

    tk.Button(
        led_frame, text="LED On", width=10,
        command=lambda: send_led_command("On"),
    ).grid(row=0, column=2, padx=5, pady=2)

    # 라인별 밝기
    bright_frame = tk.LabelFrame(parent, text="라인별 밝기 (0~100)", padx=10, pady=10)
    bright_frame.pack(fill="x", pady=(10, 0))

    state.brightness_lines = []

    for i in range(7):
        line_label = tk.Label(bright_frame, text=f"라인 {i + 1}")
        line_label.grid(row=i, column=0, sticky="w", pady=2)

        var = tk.IntVar(value=100)
        scale = tk.Scale(
            bright_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=var,
            length=180,
            showvalue=False,
        )
        scale.grid(row=i, column=1, sticky="we", padx=(5, 5))

        entry = tk.Entry(bright_frame, width=4)
        entry.grid(row=i, column=2, sticky="w")
        entry.insert(0, "100")

        def on_scale_move(value, v=var, e=entry):
            e.delete(0, tk.END)
            e.insert(0, str(v.get()))

        def on_entry_change(event, v=var, e=entry):
            txt = e.get().strip()
            try:
                val = int(txt)
            except ValueError:
                val = v.get()
            val = max(0, min(100, val))
            v.set(val)
            e.delete(0, tk.END)
            e.insert(0, str(val))

        scale.config(command=on_scale_move)
        entry.bind("<Return>", on_entry_change)
        entry.bind("<FocusOut>", on_entry_change)

        state.brightness_lines.append({"var": var, "scale": scale, "entry": entry})

    tk.Button(
        bright_frame,
        text="밝기 적용 (보드 전송 자리)",
        command=apply_brightness_from_gui,
    ).grid(row=7, column=0, columnspan=3, sticky="we", pady=(8, 0))

    # 보조 장치 제어
    control_frame = tk.LabelFrame(parent, text="보조 장치 제어", padx=10, pady=10)
    control_frame.pack(fill="x", pady=(10, 0))

    tk.Label(control_frame, text="양액 펌프").grid(row=0, column=0, sticky="w")
    tk.Button(
        control_frame, text="ON", width=8,
        command=lambda: send_pump_command(True),
    ).grid(row=0, column=1, padx=(5, 2), pady=2)
    tk.Button(
        control_frame, text="OFF", width=8,
        command=lambda: send_pump_command(False),
    ).grid(row=0, column=2, padx=(2, 5), pady=2)

    tk.Label(control_frame, text="UV 필터").grid(row=1, column=0, sticky="w")
    tk.Button(
        control_frame, text="ON", width=8,
        command=lambda: send_uv_command(True),
    ).grid(row=1, column=1, padx=(5, 2), pady=2)
    tk.Button(
        control_frame, text="OFF", width=8,
        command=lambda: send_uv_command(False),
    ).grid(row=1, column=2, padx=(2, 5), pady=2)
