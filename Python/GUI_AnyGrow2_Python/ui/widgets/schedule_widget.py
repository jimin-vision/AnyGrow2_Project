# ui/widgets/schedule_widget.py
import copy
from PyQt5 import QtCore, QtGui, QtWidgets

from ui.constants import CROP_INFO
from core import schedule_logic as sched

class ScheduleWidget(QtWidgets.QGroupBox):
    # Signals
    apply_schedule = QtCore.pyqtSignal(list)
    schedule_enabled_changed = QtCore.pyqtSignal(bool)
    
    def __init__(self, parent=None):
        super().__init__("조명 스케줄 (작물 프리셋 + 수동 설정)", parent)
        
        self.current_focus_row_index = 0
        self._crop_info = CROP_INFO

        sched_v = QtWidgets.QVBoxLayout(self)
        sched_v.setSpacing(0)

        # Top row: checkbox and status
        row0 = QtWidgets.QHBoxLayout()
        self.chk_schedule_enabled = QtWidgets.QCheckBox("스케줄 사용")
        self.chk_schedule_enabled.setChecked(True)
        self.chk_schedule_enabled.stateChanged.connect(
            lambda state: self.schedule_enabled_changed.emit(state == QtCore.Qt.Checked)
        )
        self.lbl_schedule_status = QtWidgets.QLabel("스케줄 사용 안 함")
        row0.addWidget(self.chk_schedule_enabled)
        row0.addWidget(self.lbl_schedule_status)
        row0.addStretch(1)
        sched_v.addLayout(row0)

        # Crop preset tabs
        row1 = QtWidgets.QHBoxLayout()
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setMinimumHeight(105)
        self.btn_add_crop = QtWidgets.QPushButton("+ 작물 탭 추가")
        self.btn_add_crop.clicked.connect(self.add_crop_tab)
        row1.addWidget(self.tabs, 1)
        row1.addWidget(self.btn_add_crop, 0)
        sched_v.addLayout(row1)

        for code in ("lettuce", "basil", "cherry_tomato", "strawberry"):
            if code in self._crop_info:
                self.create_crop_tab(code)

        sched_v.addWidget(QtWidgets.QLabel("(시간 형식: HH:MM, 24시간제)"))

        # Manual schedule table
        table_wrap = QtWidgets.QWidget()
        table_wrap.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        self.grid_sched = QtWidgets.QGridLayout(table_wrap)
        self._setup_schedule_grid()
        sched_v.addWidget(table_wrap)

        # Bottom buttons
        btn_row = QtWidgets.QHBoxLayout()
        self.btn_apply_schedule = QtWidgets.QPushButton("표 내용으로 스케줄 적용")
        self.btn_add_row = QtWidgets.QPushButton("+ 구간 추가")
        self.btn_del_row = QtWidgets.QPushButton("- 구간 제거")

        self.btn_apply_schedule.clicked.connect(self._emit_apply_schedule)
        self.btn_add_row.clicked.connect(self.add_schedule_row)
        self.btn_del_row.clicked.connect(self.remove_schedule_row)

        btn_row.addWidget(self.btn_apply_schedule)
        btn_row.addWidget(self.btn_add_row)
        btn_row.addWidget(self.btn_del_row)
        btn_row.addStretch(1)
        sched_v.addLayout(btn_row)

        sched_v.addStretch(1)

    def _setup_schedule_grid(self):
        self.grid_sched.setHorizontalSpacing(6)
        self.grid_sched.setVerticalSpacing(6)
        self.grid_sched.setAlignment(QtCore.Qt.AlignLeft)

        self.grid_sched.setColumnMinimumWidth(0, 35)
        self.grid_sched.setColumnMinimumWidth(1, 70)
        self.grid_sched.setColumnMinimumWidth(2, 70)
        self.grid_sched.setColumnMinimumWidth(3, 90)

        self.grid_sched.setColumnStretch(4, 1)
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.grid_sched.addWidget(spacer, 0, 4, 50, 1)

        self.grid_sched.addWidget(QtWidgets.QLabel("구간"), 0, 0)
        self.grid_sched.addWidget(QtWidgets.QLabel("시작"), 0, 1)
        self.grid_sched.addWidget(QtWidgets.QLabel("종료"), 0, 2)
        self.grid_sched.addWidget(QtWidgets.QLabel("모드"), 0, 3)

        self.schedule_rows = []
        for _ in range(3):
            self.add_schedule_row()

    def add_schedule_row(self):
        idx = len(self.schedule_rows)
        row = idx + 1

        lbl_idx = QtWidgets.QLabel(str(idx + 1))
        lbl_idx.setFixedWidth(30)
        lbl_idx.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)

        e_start = QtWidgets.QLineEdit()
        e_end = QtWidgets.QLineEdit()
        e_start.setFixedWidth(60)
        e_end.setFixedWidth(60)

        cb_mode = QtWidgets.QComboBox()
        cb_mode.addItems(["On", "Mood", "Off"])
        cb_mode.setCurrentText("On")
        cb_mode.setFixedWidth(85)

        for w in (e_start, e_end, cb_mode):
            w.setProperty("row_index", idx)
            w.installEventFilter(self)

        self.grid_sched.addWidget(lbl_idx, row, 0)
        self.grid_sched.addWidget(e_start, row, 1)
        self.grid_sched.addWidget(e_end, row, 2)
        self.grid_sched.addWidget(cb_mode, row, 3)

        self.schedule_rows.append(
            {"lbl": lbl_idx, "start": e_start, "end": e_end, "mode": cb_mode}
        )
        
        self.window().updateGeometry()
        self.window().adjustSize()

    def remove_schedule_row(self):
        if len(self.schedule_rows) <= 3: return

        last = self.schedule_rows.pop()
        for k in ("lbl", "start", "end", "mode"):
            w = last[k]
            self.grid_sched.removeWidget(w)
            w.deleteLater()

        for i, row in enumerate(self.schedule_rows):
            row["lbl"].setText(str(i + 1))
            for w in (row["start"], row["end"], row["mode"]):
                w.setProperty("row_index", i)

        if self.current_focus_row_index >= len(self.schedule_rows):
            self.current_focus_row_index = len(self.schedule_rows) - 1
            
        self.window().updateGeometry()
        self.window().adjustSize()

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.FocusIn:
            idx = obj.property("row_index")
            if isinstance(idx, int):
                self.current_focus_row_index = idx
        return super().eventFilter(obj, event)

    def _emit_apply_schedule(self):
        entries = []
        for row in self.schedule_rows:
            s_txt = row["start"].text().strip()
            e_txt = row["end"].text().strip()
            mode = row["mode"].currentText()
            if not s_txt or not e_txt:
                continue
            entries.append({"start": s_txt, "end": e_txt, "mode": mode})
        self.apply_schedule.emit(entries)

    def fill_preset_and_apply(self, crop_code: str, stage_code: str):
        try:
            preset_entries = sched.get_preset(crop_code, stage_code)
        except ValueError as e:
            QtWidgets.QMessageBox.critical(self, "프리셋 오류", str(e))
            return

        base = self.current_focus_row_index or 0
        needed = base + len(preset_entries)

        while len(self.schedule_rows) < needed:
            self.add_schedule_row()

        for i, e in enumerate(preset_entries):
            idx = base + i
            self.schedule_rows[idx]["start"].setText(e["start"])
            self.schedule_rows[idx]["end"].setText(e["end"])
            self.schedule_rows[idx]["mode"].setCurrentText(e["mode"])

        self._emit_apply_schedule()

    def create_crop_tab(self, crop_code: str):
        display_name, desc = self._crop_info[crop_code]

        tab = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(tab)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(6)
        v.addWidget(QtWidgets.QLabel(desc))
        row = QtWidgets.QHBoxLayout()
        v.addLayout(row)

        b1 = QtWidgets.QPushButton("묘목 모드")
        b2 = QtWidgets.QPushButton("생육 모드")
        b3 = QtWidgets.QPushButton("개화/열매 모드")

        b1.clicked.connect(lambda: self.fill_preset_and_apply(crop_code, "seedling"))
        b2.clicked.connect(lambda: self.fill_preset_and_apply(crop_code, "vegetative"))
        b3.clicked.connect(lambda: self.fill_preset_and_apply(crop_code, "flowering"))

        row.addWidget(b1)
        row.addWidget(b2)
        row.addWidget(b3)
        row.addStretch(1)

        self.tabs.addTab(tab, display_name)

    def add_crop_tab(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "작물 추가", "새 작물 이름을 입력하세요:")
        if not ok or not name.strip():
            return

        code_key = name.strip().replace(" ", "_")
        if code_key in self._crop_info:
            QtWidgets.QMessageBox.warning(self, "작물 추가", "이미 같은 이름의 작물이 있습니다.")
            return

        if "lettuce" in sched.PRESETS:
            sched.PRESETS[code_key] = copy.deepcopy(sched.PRESETS["lettuce"])
        else:
            sched.PRESETS[code_key] = {"seedling": [], "vegetative": [], "flowering": []}

        self._crop_info[code_key] = (name.strip(), "사용자 정의 작물")
        self.create_crop_tab(code_key)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)

    def is_enabled(self) -> bool:
        return self.chk_schedule_enabled.isChecked()

    def set_status_text(self, text: str):
        self.lbl_schedule_status.setText(text)
        
    def set_enabled(self, enabled: bool):
        self.chk_schedule_enabled.setChecked(enabled)
