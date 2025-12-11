# anygrow_gui.py
# AnyGrow2 Python GUI (정리 버전 + 시리얼 재연결 버튼)

import time
from datetime import datetime
import copy

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

import hardware as hw
import schedule_logic as sched

# ------------------------------------------------------------
# 상수
# ------------------------------------------------------------
BAR_WIDTH = 200
BAR_HEIGHT = 18

MAX_TEMP = 40.0
MAX_HUM = 100.0
MAX_CO2 = 2000.0
MAX_ILLUM = 5000.0  # 막대 그래프 스케일용 (실제 센서 최대랑 약간 달라도 무방)

CROP_INFO = {
    "lettuce": ("상추", "엽채류, 14~16h 장일에서 잘 자람"),
    "basil": ("바질", "허브류, 16h 장일 선호"),
    "cherry_tomato": ("방울토마토", "열매채소, 14~16h 빛"),
    "strawberry": ("딸기", "장일성 품종 기준, 12~16h 빛"),
}

# ------------------------------------------------------------
# 전역 변수 (GUI 구성 후 실제로 채워짐)
# ------------------------------------------------------------
root = None

status_var = None
raw_data_var = None
request_counter_var = None
sensor_status_var = None

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
schedule_rows = []
current_focus_row_index = 0

schedule_frame = None
apply_btn = None
add_btn = None
del_btn = None
notebook = None

bar_widgets = {}
brightness_lines = []
current_led_mode = "Off"

_last_console_print_time = 0.0


# ============================================================
# 1. 막대 그래프 / LED / 펌프 / UV / 밝기 보조 함수
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
        ratio = max(0.0, min(1.0, float(value) / float(max_val)))
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


def send_pump_command(on: bool):
    try:
        hw.send_pump(on)
        status_var.set(f"양액 펌프: {'On' if on else 'Off'} 명령 전송")
    except Exception as e:
        status_var.set(f"[ERROR] 양액 펌프 제어 실패: {e}")
        messagebox.showerror("Pump Error", str(e))


def send_uv_command(on: bool):
    try:
        hw.send_uv(on)
        status_var.set(f"UV 필터: {'On' if on else 'Off'} 명령 전송")
    except Exception as e:
        status_var.set(f"[ERROR] UV 필터 제어 실패: {e}")
        messagebox.showerror("UV Error", str(e))


def apply_brightness_from_gui():
    """밝기 슬라이더 값들을 모아서 hardware.apply_brightness_levels 로 전달."""
    levels = []
    for line in brightness_lines:
        v = line["var"].get()
        try:
            iv = int(v)
        except (TypeError, ValueError):
            iv = 0
        iv = max(0, min(100, iv))
        levels.append(iv)

    try:
        hw.apply_brightness_levels(levels)
        status_var.set(f"[BRIGHT] 7 라인 밝기 적용 요청: {levels}")
    except Exception as e:
        status_var.set(f"[ERROR] 밝기 적용 실패: {e}")
        messagebox.showerror("Brightness Error", str(e))


# ============================================================
# 2. 스케줄 행 / 포커스 / 작물 프리셋
# ============================================================
def set_focus_row(idx: int):
    global current_focus_row_index
    current_focus_row_index = idx


def add_schedule_row():
    """스케줄 표에 한 줄 추가."""
    global schedule_rows, manual_start_vars, manual_end_vars, manual_mode_vars
    global apply_btn, add_btn, del_btn

    idx = len(schedule_rows)
    row = 4 + idx  # 헤더 4줄 이후부터 본문

    start_var = tk.StringVar()
    end_var = tk.StringVar()
    mode_var = tk.StringVar(value="On")

    lbl = tk.Label(schedule_frame, text=str(idx + 1), width=3, anchor="w")
    e_start = tk.Entry(schedule_frame, textvariable=start_var, width=6)
    e_end = tk.Entry(schedule_frame, textvariable=end_var, width=6)
    opt = ttk.Combobox(
        schedule_frame,
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
        return lambda event: set_focus_row(i)

    e_start.bind("<FocusIn>", _make_focus_handler(idx))
    e_end.bind("<FocusIn>", _make_focus_handler(idx))
    opt.bind("<FocusIn>", _make_focus_handler(idx))

    schedule_rows.append((lbl, e_start, e_end, opt))
    manual_start_vars.append(start_var)
    manual_end_vars.append(end_var)
    manual_mode_vars.append(mode_var)

    # 버튼 위치 재배치
    last_row = 4 + len(schedule_rows) + 1
    if apply_btn is not None:
        apply_btn.grid(row=last_row, column=0, pady=(5, 0), sticky="w")
    if add_btn is not None:
        add_btn.grid(row=last_row, column=1, pady=(5, 0), sticky="w")
    if del_btn is not None:
        del_btn.grid(row=last_row, column=2, pady=(5, 0), sticky="w")


def remove_schedule_row():
    """마지막 행 제거 (최소 3줄은 남김)."""
    global schedule_rows, manual_start_vars, manual_end_vars, manual_mode_vars
    global current_focus_row_index, apply_btn, add_btn, del_btn

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
    last_row = 4 + len(schedule_rows) + 1
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
    if not schedule_enabled_var.get():
        schedule_status_var.set("스케줄 사용 안 함")
        return

    mode = sched.get_mode_for_now()
    if mode is None:
        schedule_status_var.set("스케줄 없음")
        return

    try:
        hw.send_led_packet(mode)
        schedule_status_var.set(
            f"현재 시간 기준 모드 적용: {mode} ({datetime.now().strftime('%H:%M')})"
        )
    except Exception as e:
        schedule_status_var.set(f"[ERROR] 스케줄 적용 실패: {e}")
        messagebox.showerror("Schedule Error", str(e))


def schedule_tick():
    """30초마다 스케줄 자동 체크."""
    try:
        if schedule_enabled_var.get():
            mode = sched.get_mode_for_now()
            if mode is not None:
                hw.send_led_packet(mode)
                schedule_status_var.set(
                    f"자동 스케줄 적용 중: {mode} ({datetime.now().strftime('%H:%M')})"
                )
            else:
                schedule_status_var.set("스케줄 없음")
        else:
            schedule_status_var.set("스케줄 사용 안 함")
    except Exception as e:
        schedule_status_var.set(f"[ERROR] 자동 스케줄 실패: {e}")

    root.after(30000, schedule_tick)


# ============================================================
# 3. 작물 탭
# ============================================================
def create_crop_tab(crop_code):
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
# 4. 센서 폴링 루프
# ============================================================
def poll_serial():
    """하드웨어에서 한 번 폴링 후 GUI + 콘솔 업데이트."""
    global _last_console_print_time

    try:
        reading, raw_string, request_sent, age_sec = hw.poll_sensor_once()
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

    # 센서 상태 문구
    if age_sec is None:
        sensor_status_var.set("센서 데이터 수신 기록 없음")
    else:
        if age_sec < 5.0:
            sensor_status_var.set(f"센서 통신 정상 (마지막 수신 {age_sec:4.1f}초 전)")
        else:
            sensor_status_var.set(
                f"⚠ 센서 데이터 안 들어옴 (마지막 수신 {age_sec:4.1f}초 전)"
            )

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

        # 콘솔에도 1초에 한 번 정도만 깔끔하게 출력
        now = time.time()
        if now - _last_console_print_time >= 1.0:
            print(
                f"[SENSOR] T={t:.1f}C, H={h:.1f}%, CO2={c}ppm, Illum={il}lx"
            )
            _last_console_print_time = now

    root.after(200, poll_serial)


def reconnect_serial():
    """
    시리얼 포트를 강제로 다시 여는 버튼용 함수.

    - 기존 포트/스레드 정리 (hw.close_serial)
    - 잠깐 쉰 다음 다시 hw.init_serial()
    - GUI 상태(요청 횟수, 센서 상태 문구 등) 초기화
    """
    global _last_console_print_time

    try:
        status_var.set("시리얼 재연결 시도 중...")
        root.update_idletasks()

        # 기존 포트/스레드 정리
        hw.close_serial()

        # 보드가 완전히 리셋될 시간 약간 주기
        time.sleep(0.3)

        # 다시 연결
        hw.init_serial()

        # GUI 상태 리셋
        request_counter_var.set("0")
        sensor_status_var.set("센서 데이터 수신 기록 없음")
        last_update_var.set("마지막 갱신: -")
        raw_data_var.set("(아직 수신된 데이터 없음)")
        _last_console_print_time = 0.0

        status_var.set(f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 재연결 완료")
    except Exception as e:
        status_var.set(f"[ERROR] 시리얼 재연결 실패: {e}")
        messagebox.showerror("Serial Reconnect Error", str(e))


# ============================================================
# 5. GUI 전체 구성 (좌: 센서/스케줄, 우: LED/밝기/펌프/UV)
# ============================================================
def build_gui():
    global root
    global status_var, raw_data_var, request_counter_var, sensor_status_var
    global temp_var, hum_var, co2_var, illum_var, last_update_var
    global schedule_enabled_var, schedule_status_var
    global schedule_frame, apply_btn, add_btn, del_btn, notebook
    global manual_start_vars, manual_end_vars, manual_mode_vars, schedule_rows
    global bar_widgets, brightness_lines

    root = tk.Tk()
    root.title("AnyGrow2 Python GUI (정리 버전)")
    # 가로 폭을 줄여 가운데 여백 최소화
    root.geometry("1050x720")

    manual_start_vars = []
    manual_end_vars = []
    manual_mode_vars = []
    schedule_rows = []
    brightness_lines = []
    bar_widgets = {}

    # 상단 상태 바
    status_var = tk.StringVar(value="프로그램 시작")
    raw_data_var = tk.StringVar(value="(아직 수신된 데이터 없음)")
    request_counter_var = tk.StringVar(value="0")
    sensor_status_var = tk.StringVar(value="센서 데이터 수신 기록 없음")

    temp_var = tk.StringVar(value="-")
    hum_var = tk.StringVar(value="-")
    co2_var = tk.StringVar(value="-")
    illum_var = tk.StringVar(value="-")
    last_update_var = tk.StringVar(value="마지막 갱신: -")

    top_frame = tk.Frame(root, padx=10, pady=5)
    top_frame.pack(fill="x")

    # 오른쪽 끝에 재연결 버튼
    tk.Button(
        top_frame,
        text="시리얼 재연결",
        command=reconnect_serial,
    ).pack(side="right", padx=(0, 5))

    tk.Label(top_frame, text="시리얼 상태:", font=("Malgun Gothic", 10, "bold")).pack(
        side="left"
    )
    tk.Label(top_frame, textvariable=status_var).pack(side="left", padx=5)

    tk.Label(top_frame, text="   센서 요청 횟수:", font=("Malgun Gothic", 10)).pack(
        side="left", padx=(20, 0)
    )
    tk.Label(top_frame, textvariable=request_counter_var).pack(side="left")

    # 메인 영역: 좌/우 패널
    main_frame = tk.Frame(root)
    main_frame.pack(fill="both", expand=True)

    left_panel = tk.Frame(main_frame, padx=10, pady=10)
    left_panel.pack(side="left", fill="both", expand=True)

    right_panel = tk.Frame(main_frame, padx=10, pady=10)
    right_panel.pack(side="right", fill="y")

    # ---------- 왼쪽: 센서 막대 + 스케줄 + RAW 패킷 ----------
    env_frame = tk.LabelFrame(left_panel, text="센서 데이터", padx=10, pady=10)
    env_frame.pack(fill="x", pady=(0, 5))

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
    tk.Label(env_frame, textvariable=sensor_status_var, fg="blue").grid(
        row=5, column=0, columnspan=3, sticky="w"
    )

    # 조명 스케줄
    schedule_frame_local = tk.LabelFrame(
        left_panel, text="조명 스케줄 (작물 프리셋 + 수동 설정)", padx=10, pady=10
    )
    schedule_frame_local.pack(fill="x", pady=(5, 5))
    global schedule_frame
    schedule_frame = schedule_frame_local

    global schedule_enabled_var, schedule_status_var
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

    # 작물 탭 + 추가 버튼
    crop_row = tk.Frame(schedule_frame)
    crop_row.grid(row=1, column=0, columnspan=5, sticky="we", pady=(5, 10))

    global notebook
    notebook_local = ttk.Notebook(crop_row)
    notebook_local.pack(side="left", fill="x", expand=True)
    notebook = notebook_local

    for code in ("lettuce", "basil", "cherry_tomato", "strawberry"):
        if code in CROP_INFO:
            create_crop_tab(code)

    tk.Button(
        crop_row,
        text="+ 작물 탭 추가",
        command=add_crop_tab,
    ).pack(side="left", padx=(5, 0))

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

    last_row = 4 + len(schedule_rows) + 1

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
    sensor_frame = tk.LabelFrame(
        left_panel, text="센서 데이터 (수신 패킷 문자열)", padx=10, pady=10
    )
    sensor_frame.pack(fill="both", expand=True, pady=(5, 0))

    sensor_text = tk.Label(
        sensor_frame,
        textvariable=raw_data_var,
        anchor="nw",
        justify="left",
        wraplength=600,
    )
    sensor_text.pack(fill="both", expand=True)

    # ---------- 오른쪽: LED 전체 / 라인별 밝기 / 펌프 / UV ----------
    led_frame = tk.LabelFrame(right_panel, text="LED 제어 (전체)", padx=10, pady=10)
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
    bright_frame = tk.LabelFrame(right_panel, text="라인별 밝기 (0~100)", padx=10, pady=10)
    bright_frame.pack(fill="x", pady=(10, 0))

    brightness_lines = []
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

        brightness_lines.append({"var": var, "scale": scale, "entry": entry})

    # 적용 버튼
    tk.Button(
        bright_frame,
        text="밝기 적용 (보드 전송 자리)",
        command=apply_brightness_from_gui,
    ).grid(row=7, column=0, columnspan=3, sticky="we", pady=(8, 0))

    # 보조 장치 제어
    control_frame = tk.LabelFrame(right_panel, text="보조 장치 제어", padx=10, pady=10)
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

    def on_close():
        try:
            hw.close_serial()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    return root


# ============================================================
# 6. 메인
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
