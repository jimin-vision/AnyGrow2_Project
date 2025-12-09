# schedule_logic.py
# 조명 스케줄 계산만 담당 (Tkinter / 하드웨어 의존 없음)

from datetime import datetime

# 내부 스케줄: [{start_min, end_min, mode}, ...]
_schedule = []


def parse_time_to_min(time_str):
    """
    'HH:MM' 문자열을 0~1439 분으로 변환.
    잘못된 형식이면 ValueError 발생.
    """
    time_str = time_str.strip()
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError("시간 형식 오류")
    h = int(parts[0])
    m = int(parts[1])
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("시간 범위 오류")
    return h * 60 + m


def is_time_in_range(start_min, end_min, now_min):
    """자정 넘어가는 구간까지 포함한 범위 체크."""
    if start_min <= end_min:
        return start_min <= now_min < end_min
    # 예: 22:00~06:00
    return now_min >= start_min or now_min < end_min


def set_schedule(entries):
    """
    스케줄을 설정한다.
    entries: [{ "start": "HH:MM", "end": "HH:MM", "mode": "On/Mood/Off" }, ...]
    잘못된 시간 형식이면 ValueError 발생.
    """
    global _schedule
    new_sched = []
    for e in entries:
        s_min = parse_time_to_min(e["start"])
        e_min = parse_time_to_min(e["end"])
        mode = e["mode"]
        new_sched.append(
            {"start_min": s_min, "end_min": e_min, "mode": mode}
        )
    _schedule = new_sched


def get_schedule():
    """현재 스케줄을 복사해서 반환."""
    return list(_schedule)


def get_mode_for_now():
    """
    현재 시간 기준으로 어떤 모드가 적용되어야 하는지 반환.
    스케줄이 없으면 None, 어느 구간에도 속하지 않으면 'Off' 반환.
    """
    if not _schedule:
        return None

    now = datetime.now()
    now_min = now.hour * 60 + now.minute

    for entry in _schedule:
        if is_time_in_range(entry["start_min"], entry["end_min"], now_min):
            return entry["mode"]
    return "Off"


# ---- 프리셋 ----
def preset_seedling():
    """묘목 모드 예시 스케줄."""
    return [
        {"start": "00:00", "end": "06:00", "mode": "Off"},
        {"start": "06:00", "end": "23:59", "mode": "On"},
    ]


def preset_vegetative():
    """생육 모드 예시 스케줄."""
    return [
        {"start": "22:00", "end": "06:00", "mode": "Off"},
        {"start": "06:00", "end": "22:00", "mode": "On"},
    ]


def preset_flowering():
    """개화/열매 모드 예시 스케줄."""
    return [
        {"start": "20:00", "end": "08:00", "mode": "Off"},
        {"start": "08:00", "end": "20:00", "mode": "On"},
    ]
