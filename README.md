# 🌱 AnyGrow2 Smart Farm Manager

**AnyGrow2 기반 스마트팜 통합 모니터링 & 조명 스케줄 제어 시스템**

> 실내 재배 환경 데이터를 PC에서 실시간으로 시각화하고, 사용자 스케줄에 맞춰 조명을 자동으로 제어하여 최적의 생육 환경을 조성하는 데스크톱 애플리케이션입니다.

---

## 📝 프로젝트 개요 (Overview)

이 프로젝트는 스마트팜 운영의 효율성을 높이기 위해 개발되었습니다. 핵심 센서 데이터를 수치와 직관적인 그래프로 모니터링하며, 복잡한 조명 제어를 자동화 스케줄링 시스템으로 해결하여 운영자의 부담을 줄이는 것을 목표로 합니다.

## ✨ 주요 기능 (Key Features)

### 1. 📊 실시간 환경 모니터링 (Real-time Monitoring)
* **4대 핵심 센서 데이터 수집:** 온도(°C), 습도(%), CO₂(ppm), 조도(lx) 데이터를 실시간으로 수신합니다.
* **데이터 시각화:** 단순 텍스트가 아닌 **동적 막대그래프(Bar Chart)**를 통해 현재 수치의 비율과 변화 흐름을 한눈에 파악할 수 있습니다.
* **즉각적 상태 확인:** 데이터 수신 여부와 이상 징후를 UI에서 즉시 확인할 수 있습니다.

### 2. 💡 지능형 조명 스케줄링 (Smart Lighting Control)
* **스케줄 기반 자동화:** 사용자가 설정한 시간표에 따라 **LED 모드(Off / Mood / On)**가 자동으로 전환됩니다.
* **유연한 설정:**
  * **프리셋(Preset):** 작물 및 상황에 맞는 기본 스케줄 원클릭 적용
  * **커스텀(Custom):** 시작/종료 시간을 직접 입력하여 구간 설정
* **심야 구간 대응:** 자정(00:00)을 넘어가는 시간대 설정도 완벽하게 처리하여 24시간 끊김 없는 스케줄링을 지원합니다.

### 3. 🔌 통신 안정성 확보 (Connection Recovery)
* **자동 재연결(Auto-Reconnection):** 케이블 접촉 불량이나 포트 오류로 시리얼 연결이 끊길 경우, 프로그램 종료 없이 자동으로 재연결을 시도하여 시스템 복구 능력을 강화했습니다.

---

## 🛠 시스템 동작 흐름 (Workflow)

1. **Connection**: PC와 제어 보드를 시리얼(Serial) 통신으로 연결합니다.
2. **Data Parsing**: 수신된 센서 데이터를 파싱하여 GUI 화면(수치/그래프)에 업데이트합니다.
3. **Schedule Logic**: 현재 시간과 등록된 스케줄을 비교하여 목표 조명 모드를 계산합니다.
4. **Auto Control**: 계산된 모드값(Off/Mood/On)을 장비로 전송하여 LED 상태를 변경합니다.

---

## 💻 개발 환경 (Tech Stack)

* **Language: Python, Java**
* **Framework: PyQt, Java**
* **Communication:** Serial (UART)
* **Hardware: AnyGrow2 Board** 

---

## 📸 실행 화면 (Screenshots)

*(<img width="4032" height="3024" alt="image" src="https://github.com/user-attachments/assets/87b5a5df-12ad-4b01-9b1f-894d58108c12" />
)*

| 모니터링 화면 | 스케줄 설정 화면 |
| :---: | :---: |
| ![Monitoring]<img width="821" height="609" alt="image" src="https://github.com/user-attachments/assets/2a368eb5-c67a-449b-bb49-b9e6165c702d" />
) | ![Scheduling]<img width="824" height="608" alt="image" src="https://github.com/user-attachments/assets/9904ec33-d3cd-480e-99dc-edf146b994f0" />
 |

---

## 🚀 향후 계획 (Future Plans)
* 센서 데이터 누적 로깅 및 CSV 내보내기 기능 추가
* 작물별 권장 생육 환경 프리셋 데이터베이스 확충
* 모바일 연동을 위한 네트워크 기능 확장

---

## 📝 License

This project is licensed under the MIT License.
