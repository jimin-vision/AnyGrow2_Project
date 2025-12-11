# gui/state.py
# GUI 전역 상태(루트/변수/리스트 등)를 한 곳에서 관리하는 모듈

import tkinter as tk

# Tk 루트
root = None

# 상단 상태/센서 관련 변수
status_var = None
raw_data_var = None
request_counter_var = None
sensor_status_var = None

# 센서 수치 표시 변수
temp_var = None
hum_var = None
co2_var = None
illum_var = None
last_update_var = None

# 스케줄 관련 변수
schedule_enabled_var = None
schedule_status_var = None
crop_name_var = None

# 스케줄 표 관련 상태
manual_start_vars = []
manual_end_vars = []
manual_mode_vars = []
schedule_rows = []          # (lbl, e_start, e_end, opt)
current_focus_row_index = 0
schedule_frame = None
apply_btn = None
add_btn = None
del_btn = None

# 센서 막대 그래프 (조도/온도/습도/CO2)
# key: "temp"/"hum"/"co2"/"illum" → (canvas, rect, value_label)
bar_widgets = {}

# 라인별 밝기 슬라이더/입력창
# 각 요소: {"var": tk.IntVar, "scale": Scale, "entry": Entry}
brightness_lines = []


def init_root():
    """Tk 루트 생성 및 반환."""
    global root
    if root is None:
        root = tk.Tk()
    return root


def init_vars():
    """Tk 변수 및 리스트 초기화 (매 실행 시 1번 호출)."""
    global status_var, raw_data_var, request_counter_var, sensor_status_var
    global temp_var, hum_var, co2_var, illum_var, last_update_var
    global schedule_enabled_var, schedule_status_var, crop_name_var
    global manual_start_vars, manual_end_vars, manual_mode_vars, schedule_rows
    global current_focus_row_index, schedule_frame, apply_btn, add_btn, del_btn
    global bar_widgets, brightness_lines

    status_var = tk.StringVar(value="프로그램 시작")
    raw_data_var = tk.StringVar(value="(아직 수신된 데이터 없음)")
    request_counter_var = tk.StringVar(value="0")
    sensor_status_var = tk.StringVar(value="센서 데이터 수신 기록 없음")

    temp_var = tk.StringVar(value="-")
    hum_var = tk.StringVar(value="-")
    co2_var = tk.StringVar(value="-")
    illum_var = tk.StringVar(value="-")
    last_update_var = tk.StringVar(value="마지막 갱신: -")

    schedule_enabled_var = tk.BooleanVar(value=True)
    schedule_status_var = tk.StringVar(value="스케줄 사용 안 함")
    crop_name_var = tk.StringVar(value="")

    manual_start_vars = []
    manual_end_vars = []
    manual_mode_vars = []
    schedule_rows = []
    current_focus_row_index = 0
    schedule_frame = None
    apply_btn = None
    add_btn = None
    del_btn = None

    bar_widgets = {}
    brightness_lines = []
