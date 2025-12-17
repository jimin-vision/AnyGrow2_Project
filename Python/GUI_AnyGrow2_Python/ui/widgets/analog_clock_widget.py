# ui/widgets/analog_clock_widget.py
from PyQt5 import QtCore, QtGui, QtWidgets
import math

class AnalogClockWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._time = QtCore.QTime.currentTime()
        self.setMinimumSize(100, 100)
        self.style_id = 1 # Default to style 1

    def setTime(self, time):
        if isinstance(time, QtCore.QTime):
            self._time = time
            self.update()

    def setStyle(self, style_id):
        self.style_id = style_id
        self.update()

    def paintEvent(self, event):
        side = min(self.width(), self.height())
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(side / 200.0, side / 200.0)

        if self.style_id == 1:
            self._paint_style_1(painter)
        elif self.style_id == 2:
            self._paint_style_2(painter)
        elif self.style_id == 3:
            self._paint_style_3(painter)
        elif self.style_id == 4:
            self._paint_style_4(painter)
        else:
            self._paint_style_1(painter) # Default

    def _paint_style_1(self, painter): # Classic Thick Hands
        hour_hand_color = QtGui.QColor(0, 0, 0)
        minute_hand_color = QtGui.QColor(50, 50, 50)
        second_hand_color = QtGui.QColor(255, 0, 0)
        hour_hand_poly = QtGui.QPolygonF([QtCore.QPointF(-7, 8), QtCore.QPointF(7, 8), QtCore.QPointF(0, -60)])
        minute_hand_poly = QtGui.QPolygonF([QtCore.QPointF(-4, 10), QtCore.QPointF(4, 10), QtCore.QPointF(0, -80)])

        painter.setPen(QtGui.QPen(hour_hand_color, 4))
        for i in range(12):
            painter.drawLine(88, 0, 96, 0)
            painter.rotate(30.0)
        painter.setPen(QtGui.QPen(hour_hand_color, 2))
        for j in range(60):
            if (j % 5) != 0: painter.drawLine(92, 0, 96, 0)
            painter.rotate(6.0)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(hour_hand_color))
        painter.save()
        painter.rotate(30.0 * ((self._time.hour() + self._time.minute() / 60.0)))
        painter.drawConvexPolygon(hour_hand_poly)
        painter.restore()
        
        painter.setBrush(QtGui.QBrush(minute_hand_color))
        painter.save()
        painter.rotate(6.0 * (self._time.minute() + self._time.second() / 60.0))
        painter.drawConvexPolygon(minute_hand_poly)
        painter.restore()
        
        painter.setPen(QtGui.QPen(second_hand_color, 2))
        painter.save()
        painter.rotate(6.0 * self._time.second())
        painter.drawLine(0, 10, 0, -90)
        painter.restore()
        painter.setBrush(QtGui.QBrush(second_hand_color))
        painter.drawEllipse(-3, -3, 6, 6)

    def _paint_style_2(self, painter): # Modern Line Caps
        hour_color = QtGui.QColor(50, 50, 150)
        minute_color = QtGui.QColor(100, 100, 150, 191)
        second_color = QtGui.QColor(200, 100, 100, 150)

        painter.setPen(QtGui.QPen(hour_color, 6))
        for i in range(12):
            painter.drawLine(92, 0, 96, 0)
            painter.rotate(30.0)

        painter.setPen(QtGui.QPen(hour_color, 8, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(30.0 * ((self._time.hour() + self._time.minute() / 60.0)))
        painter.drawLine(0, 0, 0, -50)
        painter.restore()

        painter.setPen(QtGui.QPen(minute_color, 5, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(6.0 * (self._time.minute() + self._time.second() / 60.0))
        painter.drawLine(0, 0, 0, -70)
        painter.restore()
        
        painter.setPen(QtGui.QPen(second_color, 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(6.0 * self._time.second())
        painter.drawLine(0, 10, 0, -80)
        painter.restore()

    def _paint_style_3(self, painter): # Minimal Thin
        line_color = QtGui.QColor(10, 10, 10)
        second_color = QtGui.QColor(150, 150, 150, 127)

        painter.setPen(line_color)
        for i in range(12):
            if i % 3 == 0:
                painter.setPen(QtGui.QPen(line_color, 3))
                painter.drawLine(85, 0, 96, 0)
            painter.rotate(30.0)

        painter.setPen(QtGui.QPen(line_color, 3, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(30.0 * ((self._time.hour() + self._time.minute() / 60.0)))
        painter.drawLine(0, 0, 0, -55)
        painter.restore()

        painter.setPen(QtGui.QPen(line_color, 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(6.0 * (self._time.minute() + self._time.second() / 60.0))
        painter.drawLine(0, 0, 0, -75)
        painter.restore()

        # No second hand for minimal style

    def _paint_style_4(self, painter): # Detailed with Numbers
        background_color = QtGui.QColor(240, 240, 240)
        number_color = QtGui.QColor(50, 50, 50)
        hour_color = QtGui.QColor(0, 0, 0)
        minute_color = QtGui.QColor(50, 50, 50)

        # Draw background
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(background_color))
        painter.drawEllipse(-99, -99, 198, 198)

        # Draw numbers
        painter.setPen(number_color)
        font = painter.font()
        font.setBold(True)
        font.setPointSize(15)
        painter.setFont(font)
        for i in range(1, 13):
            angle = i * 30.0
            _rad = angle * 3.14159 / 180.0
            x = 80 * 0.85 * math.cos(_rad)
            y = 80 * math.sin(_rad)
            painter.drawText(QtCore.QRectF(x - 15, y - 15, 30, 30), QtCore.Qt.AlignCenter, str(i))

        # Draw hour hand
        painter.setPen(QtGui.QPen(hour_color, 6, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(30.0 * ((self._time.hour() + self._time.minute() / 60.0)))
        painter.drawLine(0, 0, 0, -40)
        painter.restore()

        # Draw minute hand
        painter.setPen(QtGui.QPen(minute_color, 4, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap))
        painter.save()
        painter.rotate(6.0 * (self._time.minute() + self._time.second() / 60.0))
        painter.drawLine(0, 0, 0, -60)
        painter.restore()

        # No second hand for this style