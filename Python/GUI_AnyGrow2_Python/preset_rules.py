# preset_rules.py
# "작물 이름"을 받아서 엽채류/허브/열매채소/딸기류/기본 으로 분류하고,
# 각 카테고리/단계별로 기본 조명 프리셋(시간표)을 돌려주는 모듈

# ------------------------------------------------------------
# 1) 작물 타입별 프리셋 정의
#    - stage_code: "seedling" / "vegetative" / "flowering"
# ------------------------------------------------------------

CATEGORY_PRESETS = {
    # 엽채류(상추, 시금치, 케일 등): 16h 광 (06~22), 개화는 12h (08~20) 예시
    "leafy": {
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

    # 허브류(바질, 민트 등): 16h 광
    "herb": {
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

    # 열매채소(토마토, 방울토마토, 고추, 파프리카, 오이 등): 16h 광
    "fruit": {
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

    # 딸기류: 14h 정도 (06~20), 개화는 12h (08~20) 예시
    "strawberry": {
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

# 아무 키워드도 안 맞을 때 사용하는 기본값 (엽채류와 동일하게)
CATEGORY_PRESETS["default"] = CATEGORY_PRESETS["leafy"]

CATEGORY_LABELS = {
    "leafy": "엽채류",
    "herb": "허브류",
    "fruit": "열매채소",
    "strawberry": "딸기류",
    "default": "일반 작물",
}

# 이름 분석용 키워드들 (한글+영문 같이)
LEAFY_KEYWORDS = [
    "상추", "lettuce",
    "시금치", "spinach",
    "케일", "kale",
    "청경채", "pakchoi", "pak choi",
    "배추", "cabbage",
    "치커리", "chicory",
]

HERB_KEYWORDS = [
    "바질", "basil",
    "민트", "mint",
    "로즈마리", "rosemary",
    "세이지", "sage",
    "타임", "thyme",
    "오레가노", "oregano",
    "허브", "herb",
]

FRUIT_KEYWORDS = [
    "방울토마토", "cherry tomato", "cherrytomato",
    "토마토", "tomato",
    "파프리카", "paprika",
    "피망",
    "고추", "pepper",
    "가지", "eggplant", "aubergine",
    "오이", "cucumber",
]

STRAWBERRY_KEYWORDS = [
    "딸기", "strawberry",
]


def _detect_category(crop_name: str) -> str:
    """
    작물 이름 문자열을 보고 카테고리(leafy/herb/fruit/strawberry/default)를 추정.
    """
    name = (crop_name or "").strip().lower()
    name_k = (crop_name or "").strip()  # 한글 포함 버전

    def match_any(keywords):
        for kw in keywords:
            if kw.lower() in name or kw in name_k:
                return True
        return False

    if match_any(LEAFY_KEYWORDS):
        return "leafy"
    if match_any(HERB_KEYWORDS):
        return "herb"
    if match_any(FRUIT_KEYWORDS):
        return "fruit"
    if match_any(STRAWBERRY_KEYWORDS):
        return "strawberry"

    return "default"


def get_preset_for_crop_name(crop_name: str, stage_code: str):
    """
    작물 이름 + 생육 단계 코드("seedling","vegetative","flowering")를 받아서
    적당한 카테고리로 분류한 뒤, 그 카테고리에 해당하는 프리셋을 돌려준다.

    return: (entries, category_label)
      - entries: [{"start":"HH:MM","end":"HH:MM","mode":"On/Mood/Off"}, ...]
      - category_label: "엽채류" / "허브류" / "열매채소" / "딸기류" / "일반 작물"
    """
    category = _detect_category(crop_name)
    base = CATEGORY_PRESETS.get(category, CATEGORY_PRESETS["default"])

    if stage_code not in base:
        raise ValueError(f"해당 단계({stage_code})에 대한 프리셋이 정의되어 있지 않습니다.")

    # 원본 훼손 방지를 위해 copy
    entries = [e.copy() for e in base[stage_code]]
    label = CATEGORY_LABELS.get(category, "일반 작물")
    return entries, label
