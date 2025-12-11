# schedule_core.py
# 조명 스케줄의 "시간 계산"과 "현재 모드 판정"만 담당하는 코어 모듈

from datetime import datetime

# 내부 스케줄: [{"start_min": int, "end_min": int, "mode": str}, ...]
_schedule = []


def parse_time_to_min(time_str: str) -> int:
    """'HH:MM' -> 0~1439 분."""
    time_str = time_str.strip()
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError("시간 형식 오류: HH:MM 형태여야 합니다.")
    h = int(parts[0])
    m = int(parts[1])
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("시간 범위 오류: 00:00 ~ 23:59 사이여야 합니다.")
    return h * 60 + m


def is_time_in_range(start_min: int, end_min: int, now_min: int) -> bool:
    """자정 넘어가는 구간 포함."""
    if start_min <= end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min


def set_schedule(entries):
    """
    스케줄 설정.
    entries: [{"start": "HH:MM", "end": "HH:MM", "mode": "On/Mood/Off"}, ...]
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
    """현재 설정된 스케줄(분 단위)을 그대로 반환."""
    return list(_schedule)


def get_mode_for_now():
    """
    현재 시간 기준으로 적용해야 할 모드 반환.
    스케줄 없으면 None, 어느 구간에도 없으면 'Off'
    """
    if not _schedule:
        return None

    now = datetime.now()
    now_min = now.hour * 60 + now.minute

    for entry in _schedule:
        if is_time_in_range(entry["start_min"], entry["end_min"], now_min):
            return entry["mode"]
    return "Off"
