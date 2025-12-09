# anygrow_gui.py
# GUI + 스케줄 + 하드웨어 모듈 결합

import tkinter as tk
from tkinter import messagebox
from datetime import datetime

import hardware as hw
import schedule_logic as sched

# ---------- 전역 GUI 상태 ----------
current_led_mode = None

MAX_TEMP = 40.0
MAX_HUM = 100.0
MAX_CO2 = 2000.0
MAX_ILLUM = 5000.0
BAR_WIDTH = 220
BAR_HEIGHT = 18
bar_widgets = {}  # sensor_name -> (canvas, rect_id, value_label)

# Tk 변수들 (root 생성 후 채움)
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


# ============================================================
# 1. GUI 보조 함수 (막대/LED/스케줄)
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
    """GUI에서 호출하는 래퍼: hw 모듈 호출 + 상태 텍스트 업데이트."""
    global current_led_mode
    try:
        hw.send_led_packet(mode)
        current_led_mode = mode
        status_var.set(f"LED 명령 전송: {mode}")
    except Exception as e:
        status_var.set(f"[ERROR] LED 전송 실패: {e}")
        messagebox.showerror("LED Error", str(e))


# ---------- 스케줄 관련 ----------
def apply_manual_schedule():
    """입력칸 → sched 모듈 스케줄 설정 + 즉시 현재 모드 적용."""
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
    apply_schedule_now()


def fill_preset_and_apply(preset_name):
    """프리셋 스케줄을 입력칸에 채우고, 스케줄 설정 + 즉시 적용."""
    if preset_name == "seedling":
        entries = sched.preset_seedling()
    elif preset_name == "vegetative":
        entries = sched.preset_vegetative()
    else:
        entries = sched.preset_flowering()

    # 입력칸 초기화
    for i in range(3):
        manual_start_vars[i].set("")
        manual_end_vars[i].set("")
        manual_mode_vars[i].set("Off")

    # 프리셋 내용 채우기
    for i, e in enumerate(entries):
        if i >= 3:
            break
        manual_start_vars[i].set(e["start"])
        manual_end_vars[i].set(e["end"])
        manual_mode_vars[i].set(e["mode"])

    apply_manual_schedule()


def apply_schedule_now():
    """현재 시간 기준으로 스케줄 모드를 즉시 LED에 적용."""
    mode = sched.get_mode_for_now()
    if mode is None:
        schedule_status_var.set("스케줄 없음")
        return
    send_led_command(mode)
    schedule_status_var.set(
        "현재 시간 기준 모드 자동 적용: %s (%s)"
        % (mode, datetime.now().strftime("%H:%M"))
    )


def schedule_tick():
    """30초마다 스케줄에 따라 LED 상태 자동 변경."""
    if schedule_enabled_var.get():
        mode = sched.get_mode_for_now()
        if mode is None:
            schedule_status_var.set("스케줄 없음")
        else:
            global current_led_mode
            if mode != current_led_mode:
                send_led_command(mode)
            schedule_status_var.set(
                "스케줄 동작: %s (%s)"
                % (mode, datetime.now().strftime("%H:%M"))
            )
    else:
        schedule_status_var.set("스케줄 사용 안 함")

    root.after(30000, schedule_tick)


# ============================================================
# 2. 폴링 루프
# ============================================================
def poll_serial():
    """하드웨어 모듈에서 한 번 폴링하고, GUI 업데이트."""
    try:
        reading, raw_string, request_sent = hw.poll_sensor_once()
    except Exception as e:
        status_var.set(f"[ERROR] 센서 폴링 실패: {e}")
        root.after(1000, poll_serial)
        return

    # RAW 문자열 표시
    raw_data_var.set(raw_string)

    # 요청 카운트 증가
    if request_sent:
        try:
            cnt = int(request_counter_var.get() or "0") + 1
        except ValueError:
            cnt = 1
        request_counter_var.set(str(cnt))

    # 센서값 업데이트
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
# 3. GUI 생성
# ============================================================
def build_gui():
    global root
    global status_var, raw_data_var, request_counter_var
    global temp_var, hum_var, co2_var, illum_var, last_update_var
    global schedule_enabled_var, schedule_status_var
    global manual_start_vars, manual_end_vars, manual_mode_vars

    root = tk.Tk()
    root.title("AnyGrow2 Python GUI (분할 버전)")
    root.geometry("880x600")

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
    schedule_frame = tk.LabelFrame(root, text="조명 스케줄", padx=10, pady=10)
    schedule_frame.pack(fill="x", padx=10, pady=5)

    schedule_enabled_var = tk.BooleanVar(value=False)
    schedule_status_var = tk.StringVar(value="스케줄 사용 안 함")

    tk.Checkbutton(
        schedule_frame,
        text="스케줄 사용",
        variable=schedule_enabled_var,
    ).grid(row=0, column=0, sticky="w")

    tk.Label(schedule_frame, textvariable=schedule_status_var).grid(
        row=0, column=1, columnspan=3, sticky="w", padx=(10, 0)
    )

    tk.Label(
        schedule_frame,
        text="(시간 형식: HH:MM, 24시간제)",
    ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(0, 5))

    tk.Label(schedule_frame, text="구간").grid(row=2, column=0, sticky="w")
    tk.Label(schedule_frame, text="시작").grid(row=2, column=1, sticky="w")
    tk.Label(schedule_frame, text="종료").grid(row=2, column=2, sticky="w")
    tk.Label(schedule_frame, text="모드").grid(row=2, column=3, sticky="w")

    for i in range(3):
        tk.Label(schedule_frame, text=f"{i+1}").grid(row=3 + i, column=0, sticky="w")

        s_var = tk.StringVar(value="")
        e_var = tk.StringVar(value="")
        m_var = tk.StringVar(value="Off")

        manual_start_vars.append(s_var)
        manual_end_vars.append(e_var)
        manual_mode_vars.append(m_var)

        tk.Entry(schedule_frame, textvariable=s_var, width=6).grid(
            row=3 + i, column=1, sticky="w"
        )
        tk.Entry(schedule_frame, textvariable=e_var, width=6).grid(
            row=3 + i, column=2, sticky="w"
        )
        tk.OptionMenu(schedule_frame, m_var, "Off", "Mood", "On").grid(
            row=3 + i, column=3, sticky="w"
        )

    tk.Button(schedule_frame, text="스케줄 적용", command=apply_manual_schedule).grid(
        row=6, column=0, pady=(5, 0)
    )
    tk.Button(
        schedule_frame, text="묘목 모드", command=lambda: fill_preset_and_apply("seedling")
    ).grid(row=6, column=1, pady=(5, 0))
    tk.Button(
        schedule_frame, text="생육 모드", command=lambda: fill_preset_and_apply("vegetative")
    ).grid(row=6, column=2, pady=(5, 0))
    tk.Button(
        schedule_frame, text="개화/열매 모드", command=lambda: fill_preset_and_apply("flowering")
    ).grid(row=6, column=3, pady=(5, 0))

    # RAW 패킷 표시
    sensor_frame = tk.LabelFrame(root, text="센서 데이터 (수신 패킷 문자열)", padx=10, pady=10)
    sensor_frame.pack(fill="both", expand=True, padx=10, pady=5)

    sensor_text = tk.Label(
        sensor_frame,
        textvariable=raw_data_var,
        anchor="nw",
        justify="left",
        wraplength=840,
    )
    sensor_text.pack(fill="both", expand=True)

    # 종료 처리
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

    # 시리얼 오픈
    try:
        hw.init_serial()
        status_var.set(f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 연결됨")
    except Exception as e:
        status_var.set(f"[ERROR] 시리얼 오픈 실패: {e}")
        messagebox.showerror("Serial Error", str(e))

    root.after(200, poll_serial)
    root.after(1000, schedule_tick)
    root.mainloop()
