# ui/widgets/raw_data_widget.py

from PyQt5 import QtWidgets

class RawDataWidget(QtWidgets.QGroupBox):
    def __init__(self, parent=None):
        super().__init__("센서 데이터 (수신 패킷 문자열)", parent)

        raw_v = QtWidgets.QVBoxLayout(self)
        raw_v.setContentsMargins(8, 6, 8, 8)

        self.txt_raw = QtWidgets.QPlainTextEdit()
        self.txt_raw.setReadOnly(True)
        self.txt_raw.setPlainText("(아직 수신된 데이터 없음)")
        self.txt_raw.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth) # Enable word wrap
        raw_v.addWidget(self.txt_raw)

    def set_text(self, text: str):
        self.txt_raw.setPlainText(text)

    def reset(self):
        self.set_text("(아직 수신된 데이터 없음)")
