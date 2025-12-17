# ui/widgets/paste_template_dialog.py
from PyQt5 import QtWidgets, QtCore

class PasteTemplateDialog(QtWidgets.QDialog):
    # Custom result codes
    OverwriteRole = QtWidgets.QDialog.Accepted + 1

    def __init__(self, template_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("템플릿 붙여넣기")
        self.setMinimumWidth(300)

        # Remove the '?' help button from the title bar
        self.setWindowFlags(self.windowFlags() & ~QtCore.Qt.WindowContextHelpButtonHint)

        self.selected_template = None
        
        layout = QtWidgets.QVBoxLayout(self)

        # Description Label
        layout.addWidget(QtWidgets.QLabel("적용할 템플릿을 선택하세요:"))

        # ComboBox for templates
        self.cmb_templates = QtWidgets.QComboBox()
        self.cmb_templates.addItems(template_names)
        layout.addWidget(self.cmb_templates)

        # Buttons
        self.button_box = QtWidgets.QDialogButtonBox()
        btn_apply = self.button_box.addButton("적용", QtWidgets.QDialogButtonBox.AcceptRole)
        btn_overwrite = self.button_box.addButton("덮어쓰기", QtWidgets.QDialogButtonBox.ActionRole)
        btn_cancel = self.button_box.addButton("취소", QtWidgets.QDialogButtonBox.RejectRole)
        
        layout.addWidget(self.button_box)
        
        # Connect signals
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        btn_overwrite.clicked.connect(self.overwrite)

    def overwrite(self):
        """Custom slot for overwrite action."""
        self.done(self.OverwriteRole)

    def get_selection(self):
        """Returns the selected template name."""
        return self.cmb_templates.currentText()

    @staticmethod
    def get_paste_action(template_names, parent=None):
        """
        Creates and executes the dialog.
        Returns a tuple: (result_code, selected_template_name)
        result_code can be:
        - QDialog.Accepted (Apply)
        - PasteTemplateDialog.OverwriteRole (Overwrite)
        - QDialog.Rejected (Cancel)
        """
        if not template_names:
            QtWidgets.QMessageBox.information(parent, "알림", "저장된 템플릿이 없습니다.")
            return (QtWidgets.QDialog.Rejected, None)

        dialog = PasteTemplateDialog(template_names, parent)
        result = dialog.exec_()
        
        return (result, dialog.get_selection())
