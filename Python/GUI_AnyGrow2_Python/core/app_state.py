from PyQt5.QtCore import QObject, pyqtSignal

class AppState(QObject):
    """
    애플리케이션의 중앙 상태를 관리하는 클래스입니다.
    센서 데이터 및 기타 애플리케이션 상태를 저장하고,
    데이터 변경 시 시그널을 발생시켜 UI 및 다른 컴포넌트들이 반응할 수 있도록 합니다.
    """
    data_updated = pyqtSignal(dict) # 모든 센서 데이터가 업데이트될 때 발생

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sensor_data = {} # 센서 데이터를 저장할 딕셔너리
        
    def get_sensor_data(self):
        """현재 센서 데이터 딕셔너리를 반환합니다."""
        return self._sensor_data

    def update_sensor_data(self, new_data: dict):
        """
        새로운 센서 데이터로 상태를 업데이트하고 data_updated 시그널을 발생시킵니다.
        """
        updated = False
        for key, value in new_data.items():
            if self._sensor_data.get(key) != value:
                self._sensor_data[key] = value
                updated = True
        
        if updated:
            self.data_updated.emit(self._sensor_data)
            
    # 개별 센서 데이터 속성 (읽기 전용)
    @property
    def temperature(self):
        return self._sensor_data.get('temp')

    @property
    def humidity(self):
        return self._sensor_data.get('hum')
            
    @property
    def co2(self):
        return self._sensor_data.get('co2')
