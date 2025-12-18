# ui/widgets/schedule_widget.py
from PyQt5 import QtCore, QtWidgets, QtGui
from datetime import datetime
import copy
from .schedule_row_widget import ScheduleRowWidget
from .paste_template_dialog import PasteTemplateDialog

class ScheduleWidget(QtWidgets.QFrame):
    """
    요일별 스케줄을 관리하는 메인 위젯입니다.
    내부에 여러 개의 ScheduleRowWidget을 포함하고 관리합니다.
    """
    schedules_updated = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        
        self.weekdays_map = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        
        self.schedules = {
            "weekly": {day: [] for day in self.weekdays_map},
            "daily": {},
            "templates": {}
        }

        today = datetime.today()
        self.today_date_str = today.strftime("%Y-%m-%d")
        self.today_weekday_str = self.weekdays_map[today.weekday()]

        self.current_mode = "weekly"
        self.current_day = self.today_weekday_str

        self.selected_row = None
        self.editing_row = None
        
        root_layout = QtWidgets.QVBoxLayout(self)
        self._setup_controls(root_layout)
        self._setup_schedule_list(root_layout)
        
    def _setup_controls(self, layout):
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.rb_mode_weekly = QtWidgets.QRadioButton("요일별")
        self.rb_mode_today = QtWidgets.QRadioButton("오늘")
        self.rb_mode_weekly.setChecked(True)
        self.rb_mode_weekly.toggled.connect(self._on_mode_changed)

        self.date_time_stack = QtWidgets.QStackedWidget()
        self.lbl_today_date = QtWidgets.QLabel(f"<b>{self.today_date_str}</b>")
        self.lbl_today_date.setAlignment(QtCore.Qt.AlignCenter)
        
        self.day_selector = QtWidgets.QComboBox()
        self.day_selector.addItems(self.schedules["weekly"].keys())
        # Set initial day to today's weekday
        today_index = self.weekdays_map.index(self.today_weekday_str)
        self.day_selector.setCurrentIndex(today_index)
        self.day_selector.setMaximumWidth(120)
        self.day_selector.currentTextChanged.connect(self._day_changed)
        
        self.date_time_stack.addWidget(self.day_selector)
        self.date_time_stack.addWidget(self.lbl_today_date)
        
        self.btn_copy = QtWidgets.QPushButton("복사")
        self.btn_paste = QtWidgets.QPushButton("붙여넣기")
        self.btn_copy.clicked.connect(self._copy_schedule)
        self.btn_paste.clicked.connect(self._paste_schedule)

        self.btn_add = QtWidgets.QPushButton("✚ 추가")
        self.btn_add.clicked.connect(self._add_row)
        
        self.btn_delete_cancel = QtWidgets.QPushButton("삭제")
        self.btn_delete_cancel.setStyleSheet("color: red;")
        self.btn_delete_cancel.clicked.connect(self._handle_delete_cancel)
        
        controls_layout.addWidget(self.rb_mode_weekly)
        controls_layout.addWidget(self.rb_mode_today)
        controls_layout.addStretch(1)
        controls_layout.addWidget(self.date_time_stack)
        controls_layout.addWidget(self.btn_copy)
        controls_layout.addWidget(self.btn_paste)
        controls_layout.addWidget(self.btn_add)
        controls_layout.addWidget(self.btn_delete_cancel)
        
        layout.addLayout(controls_layout)

    def _setup_schedule_list(self, layout):
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(250)
        scroll_widget = QtWidgets.QWidget()
        
        self.schedule_list_layout = QtWidgets.QVBoxLayout(scroll_widget)
        self.schedule_list_layout.setSpacing(4)
        self.schedule_list_layout.addStretch(1)
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

    def _copy_schedule(self):
        if not self._current_schedule_list:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setText("복사할 예약이 없습니다.")
            msg_box.setWindowTitle("알림")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
            return

        dialog = QtWidgets.QInputDialog(self)
        dialog.setWindowTitle('템플릿 저장')
        dialog.setLabelText('저장할 템플릿의 이름을 입력하세요:')
        dialog.setWindowFlags(dialog.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
        ok = dialog.exec_()
        text = dialog.textValue()
        
        if ok and text:
            template_name = text
            if "templates" not in self.schedules:
                self.schedules["templates"] = {}

            if template_name in self.schedules["templates"]:
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setIcon(QtWidgets.QMessageBox.Question)
                msg_box.setText(f"'{template_name}' 템플릿이 이미 존재합니다. 덮어쓰시겠습니까?")
                msg_box.setWindowTitle("덮어쓰기 확인")
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
                msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
                msg_box.setWindowFlags(msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
                reply = msg_box.exec_()

                if reply == QtWidgets.QMessageBox.No:
                    return

            template_data = copy.deepcopy(self._current_schedule_list)
            self.schedules["templates"][template_name] = template_data
            self.schedules_updated.emit(self.schedules)
            
            # Success message
            info_box = QtWidgets.QMessageBox(self)
            info_box.setIcon(QtWidgets.QMessageBox.Information)
            info_box.setText(f"'{template_name}' 이름으로 템플릿을 저장했습니다.")
            info_box.setWindowTitle("성공")
            info_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            info_box.setWindowFlags(info_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
            info_box.exec_()

    def _paste_schedule(self):
        templates = self.schedules.get("templates", {})
        template_names = list(templates.keys())

        result, selected_template = PasteTemplateDialog.get_paste_action(template_names, self)

        if result == QtWidgets.QDialog.Rejected or not selected_template:
            return

        template_data = templates[selected_template]
        
        if result == QtWidgets.QDialog.Accepted:
            self._current_schedule_list.extend(copy.deepcopy(template_data))
        elif result == PasteTemplateDialog.OverwriteRole:
            if self.current_mode == 'weekly':
                self.schedules[self.current_mode][self.current_day] = copy.deepcopy(template_data)
            else:
                self.schedules[self.current_mode][self.current_day] = copy.deepcopy(template_data)

        self._load_day_schedules()
        self.schedules_updated.emit(self.schedules)

    def _on_mode_changed(self, checked):
        if self.rb_mode_weekly.isChecked():
            self.current_mode = "weekly"
            self.date_time_stack.setCurrentWidget(self.day_selector)
            self.current_day = self.day_selector.currentText()
        else: # '오늘' 버튼이 선택된 경우
            self.current_mode = "daily"
            self.date_time_stack.setCurrentWidget(self.lbl_today_date)
            self.current_day = self.today_date_str
        self._load_day_schedules()

    @property
    def _current_schedule_list(self):
        if self.current_mode == "weekly":
            return self.schedules["weekly"][self.current_day]
        else:
            if self.current_day not in self.schedules["daily"]:
                self.schedules["daily"][self.current_day] = []
            return self.schedules["daily"][self.current_day]

    def _load_day_schedules(self):
        while self.schedule_list_layout.count() > 1:
            item = self.schedule_list_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        for schedule_data in self._current_schedule_list:
            self._create_and_add_row_widget(schedule_data)
        
        self.selected_row = None
        self.editing_row = None
        if hasattr(self, 'btn_add'): # Check if UI is setup
            self._update_ui_for_mode_change()

    def _create_and_add_row_widget(self, data_ref):
        new_row = ScheduleRowWidget(data_ref)
        new_row.clicked.connect(self.select_row)
        new_row.edit_mode_entered.connect(self._on_row_edit_mode)
        new_row.save_requested.connect(self._on_row_save)
        self.schedule_list_layout.insertWidget(self.schedule_list_layout.count() - 1, new_row)
        return new_row

    @QtCore.pyqtSlot(dict)
    def load_schedules(self, schedules_data):
        self.schedules = schedules_data
        # Initial day setting is now handled in _setup_controls via setCurrentIndex
        # self.day_selector.setCurrentText(self.today_weekday_str)
        self._load_day_schedules()

    def select_row(self, row_widget):
        if self.editing_row:
             return
        if self.selected_row:
            self.selected_row.set_selected(False)
        self.selected_row = row_widget
        self.selected_row.set_selected(True)

    def _day_changed(self, day):
        if self.editing_row:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.setText("현재 수정 중인 예약을 먼저 저장하거나 취소해주세요.")
            msg_box.setWindowTitle("수정 중")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
            self.day_selector.setCurrentText(self.current_day)
            return
        if not day: return
        self.current_day = day
        self._load_day_schedules()
        
    def _add_row(self):
        if self.editing_row:
            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Warning)
            msg_box.setText("현재 수정 중인 예약을 먼저 저장하거나 취소해주세요.")
            msg_box.setWindowTitle("수정 중")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
            msg_box.exec_()
            return
        current_list = self._current_schedule_list
        new_data = {
            "name": f"새 예약 {len(current_list) + 1}",
            "time": QtCore.QTime(12, 0),
            "target": "전체 LED",
            "action": "켜기 (ON)"
        }
        current_list.append(new_data)
        new_row = self._create_and_add_row_widget(new_data)
        new_row.is_new = True
        new_row.enter_edit_mode()

    def _handle_delete_cancel(self):
        if self.editing_row:
            if self.editing_row.is_new:
                data_to_remove = self.editing_row.get_data()
                if data_to_remove in self._current_schedule_list:
                    self._current_schedule_list.remove(data_to_remove)
            self.editing_row = None
            self._load_day_schedules()
            self.schedules_updated.emit(self.schedules)
        else:
            if not self.selected_row:
                msg_box = QtWidgets.QMessageBox(self)
                msg_box.setIcon(QtWidgets.QMessageBox.Information)
                msg_box.setText("삭제할 예약을 먼저 선택해주세요.")
                msg_box.setWindowTitle("알림")
                msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg_box.setWindowFlags(msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
                msg_box.exec_()
                return

            msg_box = QtWidgets.QMessageBox(self)
            msg_box.setIcon(QtWidgets.QMessageBox.Question)
            msg_box.setText("선택한 예약을 정말 삭제하시겠습니까?")
            msg_box.setWindowTitle("삭제 확인")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            msg_box.setDefaultButton(QtWidgets.QMessageBox.No)
            msg_box.setWindowFlags(msg_box.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)
            reply = msg_box.exec_()

            if reply == QtWidgets.QMessageBox.Yes:
                row_to_remove = self.selected_row
                data_to_remove = row_to_remove.get_data()
                if data_to_remove in self._current_schedule_list:
                    self._current_schedule_list.remove(data_to_remove)
                self.schedule_list_layout.removeWidget(row_to_remove)
                row_to_remove.deleteLater()
                self.selected_row = None
                self.schedules_updated.emit(self.schedules)

    def _set_current_time_on_editing_row(self):
        if self.editing_row:
            self.editing_row.setTimeNow()

    def _on_row_edit_mode(self, row_widget):
        if self.editing_row and self.editing_row is not row_widget:
            self.editing_row.enter_view_mode(from_save=False)
        self.editing_row = row_widget
        self.select_row(row_widget)
        self._update_ui_for_mode_change()

    def _on_row_save(self, row_widget):
        row_widget.is_new = False
        self.editing_row = None
        self._update_ui_for_mode_change()
        self.schedules_updated.emit(self.schedules)

    def _update_ui_for_mode_change(self):
        try:
            self.btn_add.clicked.disconnect()
        except TypeError:
            pass

        is_editing = self.editing_row is not None
        
        self.btn_delete_cancel.setText("취소" if is_editing else "삭제")
        self.btn_delete_cancel.setStyleSheet("color: black;" if is_editing else "color: red;")
        
        self.rb_mode_weekly.setDisabled(is_editing)
        self.rb_mode_today.setDisabled(is_editing)
        if self.current_mode == "weekly":
            self.day_selector.setDisabled(is_editing)

        if is_editing:
            self.btn_add.setText("현재시간")
            self.btn_add.clicked.connect(self._set_current_time_on_editing_row)
            self.btn_add.setDisabled(False)
        else:
            self.btn_add.setText("✚ 추가")
            self.btn_add.clicked.connect(self._add_row)
            self.btn_add.setDisabled(False)