# anygrow_gui.py
# 스마트팜 GUI (작물 탭 + 단계별 프리셋 + 스케줄 + 센서 모니터링)

import copy
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk, simpledialog
from datetime import datetime

import hardware as hw
import schedule_logic as sched

# ---------- 전역 GUI 상태 ----------
current_led_mode = None
current_focus_row_index = 0  # 현재 커서가 있는 스케줄 행

MAX_TEMP = 40.0
MAX_HUM = 100.0
MAX_CO2 = 2000.0
MAX_ILLUM = 5000.0
BAR_WIDTH = 220
BAR_HEIGHT = 18
bar_widgets = {}

root = None
status_var = None
raw_data_var = None
request_counter_var = None
temp_var = None
hum_var = None
co2_var = None
illum_var = None
last_update_var = None
schedule_enabled_var = None
schedule_status_var = None

manual_start_vars = []
manual_end_vars = []
manual_mode_vars = []
schedule_frame = None
schedule_rows = []      # 각 행의 위젯들
apply_btn = None
add_btn = None
del_btn = None
notebook = None

# crop 코드 ↔ 표시 이름/설명 매핑
CROP_INFO = {
    "lettuce": ("상추", "잎채소, 14~16h 장일에서 잘 자람"),
    "basil": ("바질", "허브류, 16h 장일 선호"),
    "cherry_tomato": ("방울토마토", "열매채소, 14~16h 빛"),
    "strawberry": ("딸기", "장일성 품종 기준, 12~16h 빛"),
}


# ============================================================
# 1. 막대 그래프 / LED / 스케줄 보조 함수
# ============================================================
def create_bar(parent, row, label_text, var):
    tk.Label(parent, text=label_text, width=8, anchor="w").grid(
        row=row, column=0, sticky="w"
    )
    value_label = tk.Label(parent, textvariable=var, width=12, anchor="w")
    value_label.grid(row=row, column=1, sticky="w")

    canvas = tk.Canvas(parent, width=BAR_WIDTH, height=BAR_HEIGHT, highlightthickness=1)
    canvas.grid(row=row, column=2, sticky="w", padx=(10, 0))
    rect = canvas.create_rectangle(0, 0, 0, BAR_HEIGHT, fill="#4caf50")
    return canvas, rect, value_label


def get_bar_color(sensor, value):
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
    values = {
        "temp": (t, MAX_TEMP),
        "hum": (h, MAX_HUM),
        "co2": (c, MAX_CO2),
        "illum": (il, MAX_ILLUM),
    }
    for name, (value, max_val) in values.items():
        canvas, rect, label = bar_widgets[name]
        ratio = max(0.0, min(1.0, value / max_val))
        width = int(ratio * BAR_WIDTH)
        color = get_bar_color(name, value)
        canvas.coords(rect, 0, 0, width, BAR_HEIGHT)
        canvas.itemconfig(rect, fill=color)
        label.config(fg=color)


def send_led_command(mode):
    global current_led_mode
    try:
        hw.send_led_packet(mode)
        current_led_mode = mode
        status_var.set(f"LED 명령 전송: {mode}")
    except Exception as e:
        status_var.set(f"[ERROR] LED 전송 실패: {e}")
        messagebox.showerror("LED Error", str(e))


# ---------- 스케줄 행 / 포커스 관리 ----------

def set_focus_row(idx: int):
    global current_focus_row_index
    current_focus_row_index = idx


def add_schedule_row():
    """스케줄 표에 한 줄 추가. 처음 호출할 때도 사용."""
    global schedule_rows, apply_btn, add_btn, del_btn

    row_idx = len(schedule_rows)
    grid_row = 3 + row_idx + 1  # 헤더가 row=3

    lbl = tk.Label(schedule_frame, text=str(row_idx + 1))
    lbl.grid(row=grid_row, column=0, sticky="w")

    s_var = tk.StringVar(value="")
    e_var = tk.StringVar(value="")
    m_var = tk.StringVar(value="Off")

    manual_start_vars.append(s_var)
    manual_end_vars.append(e_var)
    manual_mode_vars.append(m_var)

    e_start = tk.Entry(schedule_frame, textvariable=s_var, width=6)
    e_end = tk.Entry(schedule_frame, textvariable=e_var, width=6)
    opt = tk.OptionMenu(schedule_frame, m_var, "Off", "Mood", "On")

    e_start.grid(row=grid_row, column=1, sticky="w")
    e_end.grid(row=grid_row, column=2, sticky="w")
    opt.grid(row=grid_row, column=3, sticky="w")

    # 포커스 들어올 때 현재 행 기억
    e_start.bind("<FocusIn>", lambda e, idx=row_idx: set_focus_row(idx))
    e_end.bind("<FocusIn>", lambda e, idx=row_idx: set_focus_row(idx))
    opt.bind("<FocusIn>", lambda e, idx=row_idx: set_focus_row(idx))

    schedule_rows.append((lbl, e_start, e_end, opt))

    # 아래쪽 버튼 재배치
    last_row = 3 + len(schedule_rows) + 1
    if apply_btn is not None:
        apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")
    if add_btn is not None:
        add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")
    if del_btn is not None:
        del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")


def remove_schedule_row():
    """마지막 행 제거 (최소 3줄은 남김)."""
    global schedule_rows, current_focus_row_index

    if len(schedule_rows) <= 3:
        return

    lbl, e_start, e_end, opt = schedule_rows.pop()
    lbl.destroy()
    e_start.destroy()
    e_end.destroy()
    opt.destroy()

    manual_start_vars.pop()
    manual_end_vars.pop()
    manual_mode_vars.pop()

    # 행 번호 다시 정리
    for i, (lbl, *_rest) in enumerate(schedule_rows):
        lbl.config(text=str(i + 1))

    # 포커스 인덱스 보정
    if current_focus_row_index >= len(schedule_rows):
        current_focus_row_index = len(schedule_rows) - 1

    # 버튼 위치 재배치
    last_row = 3 + len(schedule_rows) + 1
    if apply_btn is not None:
        apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")
    if add_btn is not None:
        add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")
    if del_btn is not None:
        del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")


def apply_manual_schedule():
    """표에 입력된 내용 → 스케줄 적용 + 현재 모드 즉시 반영."""
    entries = []
    for i in range(len(manual_start_vars)):
        s_txt = manual_start_vars[i].get().strip()
        e_txt = manual_end_vars[i].get().strip()
        mode = manual_mode_vars[i].get()
        if s_txt == "" or e_txt == "":
            continue
        entries.append({"start": s_txt, "end": e_txt, "mode": mode})

    try:
        sched.set_schedule(entries)
    except ValueError as e:
        messagebox.showerror("시간 형식 오류", str(e))
        return

    schedule_status_var.set(f"스케줄 {len(entries)}개 구간 적용됨")
    schedule_enabled_var.set(True)
    apply_schedule_now()


def fill_preset_and_apply(crop_code, stage_code):
    """
    프리셋 버튼에서 호출.
    - 현재 커서가 있는 행(current_focus_row_index)부터
      프리셋에 들어있는 여러 줄을 연속으로 채운다.
    """
    try:
        preset_entries = sched.get_preset(crop_code, stage_code)
    except ValueError as e:
        messagebox.showerror("프리셋 오류", str(e))
        return

    base = current_focus_row_index or 0
    needed = base + len(preset_entries)

    # 필요한 만큼 행이 없으면 추가
    while len(schedule_rows) < needed:
        add_schedule_row()

    # 표 채우기
    for i, e in enumerate(preset_entries):
        idx = base + i
        manual_start_vars[idx].set(e["start"])
        manual_end_vars[idx].set(e["end"])
        manual_mode_vars[idx].set(e["mode"])

    apply_manual_schedule()


def apply_schedule_now():
    """현재 시간 기준 모드 즉시 적용."""
    mode = sched.get_mode_for_now()
    if mode is None:
        schedule_status_var.set("스케줄 없음")
        return
    send_led_command(mode)
    schedule_status_var.set(
        f"현재 시간 기준 모드 적용: {mode} ({datetime.now().strftime('%H:%M')})"
    )


def schedule_tick():
    """30초마다 스케줄 자동 체크."""
    if schedule_enabled_var.get():
        mode = sched.get_mode_for_now()
        if mode is None:
            schedule_status_var.set("스케줄 없음")
        else:
            global current_led_mode
            if mode != current_led_mode:
                send_led_command(mode)
            schedule_status_var.set(
                f"스케줄 동작: {mode} ({datetime.now().strftime('%H:%M')})"
            )
    else:
        schedule_status_var.set("스케줄 사용 안 함")

    root.after(30000, schedule_tick)


# ---------- 작물 탭 ----------

def create_crop_tab(crop_code):
    """기존 PRESETS / CROP_INFO 에 등록된 작물 탭 하나 생성."""
    display_name, desc = CROP_INFO[crop_code]

    tab = ttk.Frame(notebook)
    notebook.add(tab, text=display_name)

    ttk.Label(tab, text=desc).pack(anchor="w", pady=(5, 2))
    btn_row = ttk.Frame(tab)
    btn_row.pack(anchor="w", pady=(3, 5))

    ttk.Button(
        btn_row,
        text="묘목 모드",
        command=lambda c=crop_code: fill_preset_and_apply(c, "seedling"),
    ).pack(side="left", padx=(0, 5))

    ttk.Button(
        btn_row,
        text="생육 모드",
        command=lambda c=crop_code: fill_preset_and_apply(c, "vegetative"),
    ).pack(side="left", padx=(0, 5))

    ttk.Button(
        btn_row,
        text="개화/열매 모드",
        command=lambda c=crop_code: fill_preset_and_apply(c, "flowering"),
    ).pack(side="left", padx=(0, 5))

    return tab


def add_crop_tab():
    """사용자 정의 작물 탭 추가 (프리셋은 상추 기준 복사)."""
    name = simpledialog.askstring("작물 추가", "새 작물 이름을 입력하세요:")
    if not name:
        return

    code_key = name.strip().replace(" ", "_")
    if code_key in CROP_INFO:
        messagebox.showwarning("작물 추가", "이미 같은 이름의 작물이 있습니다.")
        return

    # 상추 프리셋 복사해서 기본값으로 사용
    if "lettuce" in sched.PRESETS:
        sched.PRESETS[code_key] = copy.deepcopy(sched.PRESETS["lettuce"])
    else:
        sched.PRESETS[code_key] = {
            "seedling": [],
            "vegetative": [],
            "flowering": [],
        }

    CROP_INFO[code_key] = (name, "사용자 정의 작물")

    tab = create_crop_tab(code_key)
    notebook.select(tab)


# ============================================================
# 2. 센서 폴링 루프
# ============================================================
def poll_serial():
    try:
        reading, raw_string, request_sent = hw.poll_sensor_once()
    except Exception as e:
        status_var.set(f"[ERROR] 센서 폴링 실패: {e}")
        root.after(1000, poll_serial)
        return

    raw_data_var.set(raw_string)

    if request_sent:
        try:
            cnt = int(request_counter_var.get() or "0") + 1
        except ValueError:
            cnt = 1
        request_counter_var.set(str(cnt))

    if reading is not None:
        t, h, c, il = reading
        temp_var.set(f"{t:.1f} ℃")
        hum_var.set(f"{h:.1f} %")
        co2_var.set(f"{c} ppm")
        illum_var.set(f"{il} lx")
        update_sensor_bars(t, h, c, il)
        last_update_var.set(
            datetime.now().strftime("마지막 갱신: %Y-%m-%d %H:%M:%S")
        )

    root.after(200, poll_serial)


# ============================================================
# 3. GUI 구성
# ============================================================
def build_gui():
    global root
    global status_var, raw_data_var, request_counter_var
    global temp_var, hum_var, co2_var, illum_var, last_update_var
    global schedule_enabled_var, schedule_status_var
    global schedule_frame, apply_btn, add_btn, del_btn, notebook
    global manual_start_vars, manual_end_vars, manual_mode_vars, schedule_rows

    root = tk.Tk()
    root.title("AnyGrow2 Python GUI (작물 프리셋 버전)")
    root.geometry("900x640")

    manual_start_vars = []
    manual_end_vars = []
    manual_mode_vars = []
    schedule_rows = []

    status_var = tk.StringVar(value="프로그램 시작")
    raw_data_var = tk.StringVar(value="(아직 수신된 데이터 없음)")
    request_counter_var = tk.StringVar(value="0")

    temp_var = tk.StringVar(value="-")
    hum_var = tk.StringVar(value="-")
    co2_var = tk.StringVar(value="-")
    illum_var = tk.StringVar(value="-")
    last_update_var = tk.StringVar(value="마지막 갱신: -")

    # 상단 상태 바
    top_frame = tk.Frame(root, padx=10, pady=10)
    top_frame.pack(fill="x")

    tk.Label(top_frame, text="시리얼 상태:", font=("Malgun Gothic", 10, "bold")).pack(
        side="left"
    )
    tk.Label(top_frame, textvariable=status_var).pack(side="left", padx=5)

    tk.Label(top_frame, text="   센서 요청 횟수:", font=("Malgun Gothic", 10)).pack(
        side="left", padx=(20, 0)
    )
    tk.Label(top_frame, textvariable=request_counter_var).pack(side="left")

    # 수동 LED 제어
    btn_frame = tk.LabelFrame(root, text="LED 제어 (수동)", padx=10, pady=10)
    btn_frame.pack(fill="x", padx=10, pady=5)

    tk.Button(btn_frame, text="OFF", width=10, command=lambda: send_led_command("Off")).pack(
        side="left", padx=5
    )
    tk.Button(btn_frame, text="Mood", width=10, command=lambda: send_led_command("Mood")).pack(
        side="left", padx=5
    )
    tk.Button(btn_frame, text="ON", width=10, command=lambda: send_led_command("On")).pack(
        side="left", padx=5
    )

    # 센서값 + 그래프
    env_frame = tk.LabelFrame(root, text="센서값", padx=10, pady=10)
    env_frame.pack(fill="x", padx=10, pady=5)

    temp_canvas, temp_rect, temp_label = create_bar(env_frame, 0, "온도", temp_var)
    hum_canvas, hum_rect, hum_label = create_bar(env_frame, 1, "습도", hum_var)
    co2_canvas, co2_rect, co2_label = create_bar(env_frame, 2, "CO₂", co2_var)
    illum_canvas, illum_rect, illum_label = create_bar(env_frame, 3, "조도", illum_var)

    bar_widgets["temp"] = (temp_canvas, temp_rect, temp_label)
    bar_widgets["hum"] = (hum_canvas, hum_rect, hum_label)
    bar_widgets["co2"] = (co2_canvas, co2_rect, co2_label)
    bar_widgets["illum"] = (illum_canvas, illum_rect, illum_label)

    tk.Label(env_frame, textvariable=last_update_var).grid(
        row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
    )

    # 조명 스케줄
    schedule_frame_local = tk.LabelFrame(root, text="조명 스케줄 (작물 프리셋 + 수동 설정)", padx=10, pady=10)
    schedule_frame_local.pack(fill="x", padx=10, pady=5)
    schedule_frame = schedule_frame_local

    schedule_enabled_var = tk.BooleanVar(value=True)
    schedule_status_var = tk.StringVar(value="스케줄 사용 안 함")

    tk.Checkbutton(
        schedule_frame,
        text="스케줄 사용",
        variable=schedule_enabled_var,
    ).grid(row=0, column=0, sticky="w")

    tk.Label(schedule_frame, textvariable=schedule_status_var).grid(
        row=0, column=1, columnspan=4, sticky="w", padx=(10, 0)
    )

    # ==== 작물 탭 + 추가 버튼을 한 줄에 배치 ====
    crop_row = tk.Frame(schedule_frame)
    crop_row.grid(row=1, column=0, columnspan=5, sticky="we", pady=(5, 10))

    notebook_local = ttk.Notebook(crop_row)
    notebook_local.pack(side="left", fill="x", expand=True)
    notebook = notebook_local

    for code in ("lettuce", "basil", "cherry_tomato", "strawberry"):
        create_crop_tab(code)

    tk.Button(
        crop_row,
        text="+ 작물 탭 추가",
        command=add_crop_tab,
    ).pack(side="left", padx=(5, 0))
    # =======================================

    # 수동 스케줄 표
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
        add_schedule_row()

    last_row = 3 + len(schedule_rows) + 1

    global apply_btn, add_btn, del_btn
    apply_btn = tk.Button(
        schedule_frame,
        text="표 내용으로 스케줄 적용",
        command=apply_manual_schedule,
    )
    apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")

    add_btn = tk.Button(
        schedule_frame,
        text="+ 구간 추가",
        command=add_schedule_row,
    )
    add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")

    del_btn = tk.Button(
        schedule_frame,
        text="- 구간 제거",
        command=remove_schedule_row,
    )
    del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")

    # RAW 패킷 표시
    sensor_frame = tk.LabelFrame(root, text="센서 데이터 (수신 패킷 문자열)", padx=10, pady=10)
    sensor_frame.pack(fill="both", expand=True, padx=10, pady=5)

    sensor_text = tk.Label(
        sensor_frame,
        textvariable=raw_data_var,
        anchor="nw",
        justify="left",
        wraplength=860,
    )
    sensor_text.pack(fill="both", expand=True)

    def on_close():
        try:
            hw.close_serial()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    return root


# ============================================================
# 4. 메인
# ============================================================
if __name__ == "__main__":
    root = build_gui()

    try:
        hw.init_serial()
        status_var.set(f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 연결됨")
    except Exception as e:
        status_var.set(f"[ERROR] 시리얼 오픈 실패: {e}")
        messagebox.showerror("Serial Error", str(e))

    root.after(200, poll_serial)
    root.after(1000, schedule_tick)
    root.mainloop()
