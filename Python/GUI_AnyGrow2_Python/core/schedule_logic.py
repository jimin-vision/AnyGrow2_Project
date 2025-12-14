# schedule_logic.py
# AnyGrow2 조명 스케줄 계산 전용 모듈

from datetime import datetime

# ------------------------------------------------------------
# 1) 작물별 / 생육 단계별 기본 프리셋
#    - 각 항목은 "start", "end", "mode" 로 구성
#    - mode: "On" / "Off" / "Mood"
# ------------------------------------------------------------

PRESETS = {
    "lettuce": {
        # 묘목: 16h 광 (06~22)
        "seedling": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        # 생육: 동일하게 16h
        "vegetative": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        # 개화/결구: 12h 광 (08~20)
        "flowering": [
            {"start": "08:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "08:00", "mode": "Off"},
        ],
    },
    "basil": {
        # 허브류: 16h 광
        "seedling": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        "vegetative": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        "flowering": [
            {"start": "08:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "08:00", "mode": "Off"},
        ],
    },
    "cherry_tomato": {
        # 열매채소: 14~16h 정도, 여기서는 16h 가정
        "seedling": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        "vegetative": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        "flowering": [
            {"start": "08:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "08:00", "mode": "Off"},
        ],
    },
    "strawberry": {
        # 딸기: 장일성 품종 기준 12~16h, 여기서는 14h 가정
        "seedling": [
            {"start": "06:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "06:00", "mode": "Off"},
        ],
        "vegetative": [
            {"start": "06:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "06:00", "mode": "Off"},
        ],
        "flowering": [
            {"start": "08:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "08:00", "mode": "Off"},
        ],
    },
}

# 사용자가 수동으로 설정한 스케줄이 이 변수에 저장됨.
# 내부 형식: [{"start_min": int, "end_min": int, "mode": str}, ...]
_schedule = []


def get_preset(crop_code: str, stage_code: str):
    """작물/단계 프리셋 스케줄 반환 (없는 경우 ValueError)."""
    try:
        return PRESETS[crop_code][stage_code]
    except KeyError:
        raise ValueError(f"Unknown preset: crop={crop_code}, stage={stage_code}")


# ---------- 공통 스케줄 로직 ----------

def parse_time_to_min(time_str: str) -> int:
    """'HH:MM' -> 0~1439 분."""
    time_str = time_str.strip()
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError("시간 형식 오류")
    h = int(parts[0])
    m = int(parts[1])
    if not (0 <= h < 24 and 0 <= m < 60):
        raise ValueError("시간 범위 오류")
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
