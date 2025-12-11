# gui/app.py
# AnyGrow2 GUI 전체를 조립하고 실행하는 엔트리 포인트 모듈

import tkinter as tk
from tkinter import messagebox

from . import state
from . import panels_top, panels_left, panels_right, logic

import hardware as hw


def build_gui():
    """Tk 루트 생성 + 상태/패널 구성."""
    # 루트/변수 초기화
    root = state.init_root()
    root.title("AnyGrow2 Python GUI (정리 2단계: GUI 분할)")
    root.geometry("1050x720")  # 가운데 여백 줄인 버전

    state.init_vars()

    # 상단 상태바
    panels_top.build_top_bar(root, on_reconnect=logic.reconnect_serial)

    # 메인 좌/우 패널
    main_frame = tk.Frame(root)
    main_frame.pack(fill="both", expand=True)

    left_panel = tk.Frame(main_frame, padx=10, pady=10)
    left_panel.pack(side="left", fill="both", expand=True)

    right_panel = tk.Frame(main_frame, padx=10, pady=10)
    right_panel.pack(side="right", fill="y")

    panels_left.build_left_panel(left_panel)
    panels_right.build_right_panel(right_panel)

    # 창 닫기 시 시리얼 정리
    def on_close():
        try:
            hw.close_serial()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    return root


def main():
    """프로그램 진입점."""
    root = build_gui()

    # 시리얼 초기화
    try:
        hw.init_serial()
        state.status_var.set(f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 연결됨")
    except Exception as e:
        state.status_var.set(f"[ERROR] 시리얼 오픈 실패: {e}")
        messagebox.showerror("Serial Error", str(e))

    # 주기적 센서 폴링 + 스케줄 체크
    root.after(200, logic.poll_serial)
    root.after(1000, logic.schedule_tick)

    root.mainloop()
