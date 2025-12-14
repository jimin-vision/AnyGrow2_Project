# ui/constants.py

CROP_INFO = {
    "lettuce": ("상추", "엽채류, 14~16h 장일에서 잘 자람"),
    "basil": ("바질", "허브류, 16h 장일 선호"),
    "cherry_tomato": ("방울토마토", "열매채소, 14~16h 빛"),
    "strawberry": ("딸기", "장일성 품종 기준, 12~16h 빛"),
}

# ============================================================
# 원본 JS(anygrow2_client.js) 기준 "그래프 스케일"
#   max = [35, 90, 4999, 8000]
# ============================================================
MAX_TEMP = 35.0
MAX_HUM = 90.0
MAX_CO2 = 4999.0
MAX_ILLUM = 8000.0


def get_bar_color(sensor: str, value: float) -> str:
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
