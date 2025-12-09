# schedule_logic.py
# 조명 스케줄 로직 + 작물별 프리셋

from datetime import datetime

# 내부 스케줄: [{start_min, end_min, mode}, ...]
_schedule = []

# crop/stage 코드는 영어, GUI에서 한글로 표시
# 시간은 'HH:MM' 문자열, mode는 'On' / 'Off' / 'Mood'
# 각 프리셋은 "여러 줄"일 수 있음 (On/Off 모두 표시)
#
# 단계별로 확실히 다른 패턴이 나오도록 정리:
# - 묘목: 가장 긴 조명 시간
# - 생육: 그보다 조금 짧게
# - 개화/열매: 더 짧게 (또는 다른 시간대)
PRESETS = {
    "lettuce": {  # 상추
        # 묘목: 16h On (05~21)
        "seedling": [
            {"start": "05:00", "end": "21:00", "mode": "On"},
            {"start": "21:00", "end": "05:00", "mode": "Off"},
        ],
        # 생육: 14h On (06~20)
        "vegetative": [
            {"start": "06:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "06:00", "mode": "Off"},
        ],
        # 개화/열매: 10h On (08~18) — 상추에선 실제로 잘 안 쓰지만, 단계 구분용
        "flowering": [
            {"start": "08:00", "end": "18:00", "mode": "On"},
            {"start": "18:00", "end": "08:00", "mode": "Off"},
        ],
    },

    "basil": {  # 바질
        # 묘목: 16h On (06~22)
        "seedling": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        # 생육: 14h On (07~21)
        "vegetative": [
            {"start": "07:00", "end": "21:00", "mode": "On"},
            {"start": "21:00", "end": "07:00", "mode": "Off"},
        ],
        # 개화/열매: 12h On (08~20)
        "flowering": [
            {"start": "08:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "08:00", "mode": "Off"},
        ],
    },

    "cherry_tomato": {  # 방울토마토
        # 묘목: 18h On (04~22)
        "seedling": [
            {"start": "04:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "04:00", "mode": "Off"},
        ],
        # 생육: 16h On (06~22)
        "vegetative": [
            {"start": "06:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "06:00", "mode": "Off"},
        ],
        # 개화/열매: 14h On (08~22)
        "flowering": [
            {"start": "08:00", "end": "22:00", "mode": "On"},
            {"start": "22:00", "end": "08:00", "mode": "Off"},
        ],
    },

    "strawberry": {  # 딸기
        # 묘목: 16h On (05~21)
        "seedling": [
            {"start": "05:00", "end": "21:00", "mode": "On"},
            {"start": "21:00", "end": "05:00", "mode": "Off"},
        ],
        # 생육: 14h On (06~20)
        "vegetative": [
            {"start": "06:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "06:00", "mode": "Off"},
        ],
        # 개화/열매: 12h On (08~20)
        "flowering": [
            {"start": "08:00", "end": "20:00", "mode": "On"},
            {"start": "20:00", "end": "08:00", "mode": "Off"},
        ],
    },
}


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
