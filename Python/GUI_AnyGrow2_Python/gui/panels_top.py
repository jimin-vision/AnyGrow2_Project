# gui/panels_top.py
# 상단 상태바 (시리얼 상태 / 센서 요청 횟수 / 재연결 버튼) 구성

import tkinter as tk
from . import state


def build_top_bar(root, on_reconnect):
    """
    상단 상태바 프레임 생성.
      - root: Tk 루트
      - on_reconnect: "시리얼 재연결" 버튼 콜백 함수
    """
    top_frame = tk.Frame(root, padx=10, pady=5)
    top_frame.pack(fill="x")

    # 오른쪽: 재연결 버튼
    tk.Button(
        top_frame,
        text="시리얼 재연결",
        command=on_reconnect,
    ).pack(side="right", padx=(0, 5))

    # 왼쪽: 상태/센서 요청 횟수
    tk.Label(
        top_frame,
        text="시리얼 상태:",
        font=("Malgun Gothic", 10, "bold"),
    ).pack(side="left")
    tk.Label(top_frame, textvariable=state.status_var).pack(side="left", padx=5)

    tk.Label(
        top_frame,
        text="   센서 요청 횟수:",
        font=("Malgun Gothic", 10),
    ).pack(side="left", padx=(20, 0))
    tk.Label(top_frame, textvariable=state.request_counter_var).pack(side="left")

    return top_frame
