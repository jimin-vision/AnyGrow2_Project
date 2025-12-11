# gui/schedule/preset_ai.py
# 작물 이름 + 단계에 따른 프리셋 적용 (현재는 규칙 기반, 나중에 진짜 AI 연동 예정)

from tkinter import messagebox

from .. import state
import ai_bridge
from . import table


def apply_ai_preset(stage_code: str):
    """
    작물 이름 입력 + (묘목/생육/개화) 버튼에서 호출되는 함수.
    - state.crop_name_var 에서 이름 읽고
    - ai_bridge.get_light_schedule 로 프리셋 가져와서
    - 표에 채운 뒤, 바로 스케줄 적용까지 수행.
    """
    name = state.crop_name_var.get().strip()
    if not name:
        messagebox.showwarning("작물 이름", "먼저 작물 이름을 입력하세요.")
        return

    try:
        entries, category_label = ai_bridge.get_light_schedule(name, stage_code)
    except ValueError as e:
        messagebox.showerror("프리셋 오류", str(e))
        return

    # 필요한 행 수 확보
    while len(state.schedule_rows) < len(entries):
        table.add_schedule_row()

    # 기존 값 초기화
    for i in range(len(state.manual_start_vars)):
        state.manual_start_vars[i].set("")
        state.manual_end_vars[i].set("")
        state.manual_mode_vars[i].set("Off")

    # 새 프리셋 채우기 (0번 행부터)
    for i, e in enumerate(entries):
        state.manual_start_vars[i].set(e["start"])
        state.manual_end_vars[i].set(e["end"])
        state.manual_mode_vars[i].set(e["mode"])

    state.schedule_status_var.set(
        f"'{name}' ({category_label}) 기준 {stage_code} 프리셋 적용"
    )
    table.apply_manual_schedule()
