# ai_bridge.py
# GUI 입장에서 "작물 이름 + 단계 → 조명 스케줄"을 얻기 위한 통합 인터페이스.
# 지금 단계에서는 실제 AI 호출은 하지 않고, preset_rules 모듈의 규칙 기반 프리셋만 사용한다.
#
# 나중에 OpenAI API 등을 붙이고 싶으면, 이 파일 안에만 코드를 추가/수정하면 된다.

from typing import List, Dict, Tuple

import preset_rules


USE_REAL_AI = False  # 나중에 True 로 바꾸면, 실제 AI 호출 코드 추가할 예정


def get_light_schedule(crop_name: str, stage_code: str) -> Tuple[List[Dict], str]:
    """
    작물 이름과 생육 단계 코드를 받아서 조명 스케줄을 돌려준다.

    현재는:
      - preset_rules.get_preset_for_crop_name() 을 호출하는 규칙 기반 구현만 있음.
    나중에:
      - USE_REAL_AI 가 True 이고, API 키/네트워크가 준비되면
        OpenAI API 를 통해 프리셋을 얻도록 확장할 수 있다.

    return: (entries, label)
      - entries: [{"start":"HH:MM","end":"HH:MM","mode":"On/Mood/Off"}, ...]
      - label: "엽채류" 등 카테고리 설명 문자열 (또는 "AI 추천 (...)" 등)
    """
    # 현재 단계: 규칙 기반 프리셋만 사용
    entries, category_label = preset_rules.get_preset_for_crop_name(
        crop_name, stage_code
    )
    return entries, category_label
