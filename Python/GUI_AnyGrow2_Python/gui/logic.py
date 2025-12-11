# gui/logic.py
# 센서 폴링 / 스케줄 자동 적용 / 시리얼 재연결 + 자동 재연결 로직

import time
from datetime import datetime
from tkinter import messagebox

from . import state, helpers
import hardware as hw
import schedule_core as sched_core

# --- 센서 수신 시간 관련 임계값 (원하면 여기 숫자만 조정해도 됨) ---
SENSOR_WARN_SEC = 5.0              # 이 이상 수신 안 되면 경고 문구
SENSOR_AUTO_RECONNECT_SEC = 30.0   # 이 이상 끊기면 자동으로 한 번 재연결 시도
SENSOR_POWER_RESET_HINT_SEC = 120.0  # 이 이상 끊기면 보드 전원 리셋 권장

_last_console_print_time = 0.0
_last_auto_reconnect_time = None  # 마지막 자동 재연결 시각 (epoch sec)


def poll_serial():
    """하드웨어에서 한 번 폴링 후 GUI + 콘솔 업데이트."""
    global _last_console_print_time, _last_auto_reconnect_time

    try:
        reading, raw_string, request_sent, age_sec = hw.poll_sensor_once()
    except Exception as e:
        state.status_var.set(f"[ERROR] 센서 폴링 실패: {e}")
        state.root.after(1000, poll_serial)
        return

    # RAW 패킷 문자열 표시
    state.raw_data_var.set(raw_string)

    # 센서 요청 카운터 증가
    if request_sent:
        try:
            cnt = int(state.request_counter_var.get() or "0") + 1
        except ValueError:
            cnt = 1
        state.request_counter_var.set(str(cnt))

    # --- 기본 센서 상태 문구 ---
    if age_sec is None:
        sensor_text = "센서 데이터 수신 기록 없음"
    else:
        if age_sec < SENSOR_WARN_SEC:
            sensor_text = f"센서 통신 정상 (마지막 수신 {age_sec:4.1f}초 전)"
        else:
            sensor_text = (
                f"⚠ 센서 데이터 안 들어옴 (마지막 수신 {age_sec:4.1f}초 전)"
            )

    # --- 자동 재연결 판단 ---
    now = time.time()
    if age_sec is not None and age_sec >= SENSOR_AUTO_RECONNECT_SEC:
        # 일정 시간 이상 수신이 없는데, 최근에 자동 재연결 한 적이 없다면 한 번 시도
        need_reconnect = False
        if _last_auto_reconnect_time is None:
            need_reconnect = True
        else:
            # 같은 문제로 계속 재연결만 반복하는 걸 막기 위해 최소 60초 간격
            if now - _last_auto_reconnect_time >= 60.0:
                need_reconnect = True

        if need_reconnect:
            _last_auto_reconnect_time = now
            # 상태바에 자동 재연결 시도 표시
            state.status_var.set("센서 장시간 무응답, 자동 재연결 중...")
            state.root.update_idletasks()

            try:
                # 동기적으로 한 번 재연결 시도 (팝업 없이)
                reconnect_serial(show_message_box=False)
            except Exception:
                # reconnect_serial 안에서 상태는 처리하므로 여기서는 무시
                pass

            # 재연결 후에도 age_sec 은 당장 바뀌지 않을 수 있으므로
            # 상태 문구는 일단 재연결 시도 사실을 담아서 표시
            sensor_text = (
                f"⚠ 센서 데이터 장시간 무응답, 자동 재연결 시도됨 "
                f"(마지막 수신 {age_sec:4.1f}초 전)"
            )

    # --- 아주 오랫동안 수신 없으면 전원 리셋 권장 문구 ---
    if age_sec is not None and age_sec >= SENSOR_POWER_RESET_HINT_SEC:
        sensor_text = (
            f"⚠ 센서 데이터 장시간 수신 없음 (마지막 수신 {age_sec:4.1f}초 전)\n"
            f"   스마트팜 본체 전원을 한 번 껐다 켜야 할 수도 있습니다."
        )

    state.sensor_status_var.set(sensor_text)

    # --- 실제 센서 값 / 그래프 / 콘솔 출력 ---
    if reading is not None:
        t, h, c, il = reading
        state.temp_var.set(f"{t:.1f} ℃")
        state.hum_var.set(f"{h:.1f} %")
        state.co2_var.set(f"{c} ppm")
        state.illum_var.set(f"{il} lx")
        helpers.update_sensor_bars(t, h, c, il)
        state.last_update_var.set(
            datetime.now().strftime("마지막 갱신: %Y-%m-%d %H:%M:%S")
        )

        # 콘솔에도 1초에 한 번 정도만 출력
        now = time.time()
        if now - _last_console_print_time >= 1.0:
            print(
                f"[SENSOR] T={t:.1f}C, H={h:.1f}%, CO2={c}ppm, Illum={il}lx"
            )
            _last_console_print_time = now

    # 다음 폴링 예약
    state.root.after(200, poll_serial)


def reconnect_serial(show_message_box: bool = True):
    """
    시리얼 포트를 강제로 다시 여는 함수.

    - 상단바의 "시리얼 재연결" 버튼에서 직접 호출할 때는 기본값(True) 그대로 사용.
    - poll_serial() 에서 자동으로 호출할 때는 show_message_box=False 로 호출해서
      팝업창은 띄우지 않는다.
    """
    global _last_console_print_time

    try:
        state.status_var.set("시리얼 재연결 중...")
        state.root.update_idletasks()

        # 기존 포트/스레드 정리
        hw.close_serial()

        # 보드가 완전히 리셋될 시간 약간 주기
        time.sleep(0.3)

        # 다시 연결
        hw.init_serial()

        # GUI 상태 리셋
        state.request_counter_var.set("0")
        state.sensor_status_var.set("센서 데이터 수신 기록 없음")
        state.last_update_var.set("마지막 갱신: -")
        state.raw_data_var.set("(아직 수신된 데이터 없음)")
        _last_console_print_time = 0.0

        state.status_var.set(
            f"[OK] 포트 {hw.SERIAL_PORT} @ {hw.BAUD_RATE} 재연결 완료"
        )
    except Exception as e:
        state.status_var.set(f"[ERROR] 시리얼 재연결 실패: {e}")
        if show_message_box:
            messagebox.showerror("Serial Reconnect Error", str(e))
        # 자동 재연결일 때는 팝업 없이 상태바만 남김


def schedule_tick():
    """30초마다 스케줄 자동 체크."""
    try:
        if state.schedule_enabled_var.get():
            mode = sched_core.get_mode_for_now()
            if mode is not None:
                hw.send_led_packet(mode)
                state.schedule_status_var.set(
                    f"자동 스케줄 적용 중: {mode} ({datetime.now().strftime('%H:%M')})"
                )
            else:
                state.schedule_status_var.set("스케줄 없음")
        else:
            state.schedule_status_var.set("스케줄 사용 안 함")
    except Exception as e:
        state.schedule_status_var.set(f"[ERROR] 자동 스케줄 실패: {e}")

    state.root.after(30000, schedule_tick)
