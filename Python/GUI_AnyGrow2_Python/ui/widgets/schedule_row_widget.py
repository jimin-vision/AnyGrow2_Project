# ui/widgets/schedule_row_widget.py
from PyQt5 import QtCore, QtWidgets, QtGui

class ScheduleRowWidget(QtWidgets.QFrame):
    """
    하나의 스케줄 예약을 표시하고 수정하는 위젯입니다.
    '보기 모드'와 '수정 모드' 사이를 전환할 수 있습니다.
    """
    edit_mode_entered = QtCore.pyqtSignal(object)  # self 전달
    save_requested = QtCore.pyqtSignal(object) # self 전달 (데이터는 직접 수정됨)
    cancel_requested = QtCore.pyqtSignal(object) # self 전달
    clicked = QtCore.pyqtSignal(object) # self 전달, for selection
    
    def __init__(self, data_ref, parent=None): # schedule_data -> data_ref
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setObjectName("ScheduleRowWidget")
        
        # 데이터의 참조를 직접 저장
        self.data = data_ref

        # 사용 가능한 기능 목록 (나중에 외부에서 주입받아야 함)
        self.available_targets = ["전체 LED", "양액 펌프", "UV 필터"]
        
        self.main_layout = QtWidgets.QStackedLayout(self)
        
        self._setup_view_mode()
        self._setup_edit_mode()
        
        # Add widgets to the stacked layout
        self.main_layout.addWidget(self.view_widget)
        self.main_layout.addWidget(self.edit_widget)
        
        self.main_layout.setCurrentWidget(self.view_widget)
        self.is_selected = False
        self.is_editing = False
        self.is_new = False


    def _setup_view_mode(self):
        """읽기 전용 모드의 UI를 설정합니다."""
        self.view_widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(self.view_widget)
        layout.setContentsMargins(8, 4, 8, 4)
        
        self.lbl_name = QtWidgets.QLabel(self.data["name"])
        self.lbl_name.setWordWrap(True)
        self.lbl_name.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        
        self.lbl_time = QtWidgets.QLabel(self.data["time"].toString("HH:mm"))
        self.lbl_target = QtWidgets.QLabel(self.data["target"])
        self.lbl_action = QtWidgets.QLabel(self.data["action"])
        
        self.btn_edit = QtWidgets.QPushButton("수정")
        self.btn_edit.setFixedWidth(60)
        self.btn_edit.clicked.connect(self.enter_edit_mode)

        layout.addWidget(self.lbl_name, 2) # 이름이 가장 많은 공간을 차지하도록
        layout.addWidget(self.lbl_time, 1)
        layout.addWidget(self.lbl_target, 1)
        layout.addWidget(self.lbl_action, 1)
        layout.addWidget(self.btn_edit, 0)

    def _setup_edit_mode(self):
        """수정 모드의 UI를 설정합니다."""
        self.edit_widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(self.edit_widget)
        layout.setContentsMargins(8, 4, 8, 4)

        self.edit_name = QtWidgets.QLineEdit(self.data["name"])
        
        # Time input with two spin boxes
        self.spin_hour = QtWidgets.QSpinBox()
        self.spin_hour.setRange(0, 23)
        self.spin_hour.setSuffix("시")
        self.spin_min = QtWidgets.QSpinBox()
        self.spin_min.setRange(0, 59)
        self.spin_min.setSuffix("분")

        time_layout = QtWidgets.QHBoxLayout()
        time_layout.setSpacing(2)
        time_layout.addWidget(self.spin_hour)
        time_layout.addWidget(QtWidgets.QLabel(" : "))
        time_layout.addWidget(self.spin_min)
        time_layout.addStretch(1)

        self.cmb_target = QtWidgets.QComboBox()
        self.cmb_target.addItems(self.available_targets)
        
        self.cmb_action = QtWidgets.QComboBox()
        self.cmb_action.addItems(["켜기 (ON)", "끄기 (OFF)"])

        self.btn_save = QtWidgets.QPushButton("저장")
        self.btn_save.setFixedWidth(60)
        self.btn_save.clicked.connect(self._save_changes)
        
        layout.addWidget(self.edit_name, 3)
        layout.addLayout(time_layout, 2)
        layout.addWidget(self.cmb_target, 2)
        layout.addWidget(self.cmb_action, 2)
        layout.addWidget(self.btn_save, 0)

    def setTimeNow(self):
        """Sets the time spin boxes to the current time. Public method."""
        now = QtCore.QTime.currentTime()
        self.spin_hour.setValue(now.hour())
        self.spin_min.setValue(now.minute())

    def enter_view_mode(self, from_save=False):
        """보기 모드로 전환합니다."""
        if from_save:
            # 참조된 딕셔너리를 직접 수정 (in-place update)
            self.data["name"] = self.edit_name.text()
            self.data["time"] = QtCore.QTime(self.spin_hour.value(), self.spin_min.value())
            self.data["target"] = self.cmb_target.currentText()
            self.data["action"] = self.cmb_action.currentText()
            
            # UI 라벨 업데이트
            self.lbl_name.setText(self.data["name"])
            self.lbl_time.setText(self.data["time"].toString("HH:mm"))
            self.lbl_target.setText(self.data["target"])
            self.lbl_action.setText(self.data["action"])
        
        self.is_editing = False
        self.main_layout.setCurrentWidget(self.view_widget)
        
    def enter_edit_mode(self):
        """수정 모드로 전환합니다."""
        # 현재 데이터로 수정 위젯들 값 설정
        self.edit_name.setText(self.data["name"])
        self.spin_hour.setValue(self.data["time"].hour())
        self.spin_min.setValue(self.data["time"].minute())
        self.cmb_target.setCurrentText(self.data["target"])
        self.cmb_action.setCurrentText(self.data["action"])
        
        self.is_editing = True
        self.main_layout.setCurrentWidget(self.edit_widget)
        self.edit_mode_entered.emit(self) # 수정 모드 진입 시그널 발생

    def _save_changes(self):
        """변경 사항을 저장하고 보기 모드로 돌아갑니다."""
        self.enter_view_mode(from_save=True) # 데이터 직접 수정
        self.save_requested.emit(self) # 저장 완료 신호 발생


    def mousePressEvent(self, event: QtGui.QMouseEvent):
        """위젯이 클릭되었을 때 선택 신호를 보냅니다."""
        if not self.is_editing:
            self.clicked.emit(self)
        super().mousePressEvent(event)
        
    def set_selected(self, selected: bool):
        """선택 상태에 따라 스타일시트를 변경합니다."""
        self.is_selected = selected
        if selected:
            self.setStyleSheet("#ScheduleRowWidget { border: 1.5px solid #4D98E2; }")
        else:
            self.setStyleSheet("#ScheduleRowWidget { border: 1px solid #AAAAAA; }")

    def get_data(self):
        return self.data
