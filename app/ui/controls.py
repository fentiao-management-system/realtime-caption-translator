"""自定义控件：发光按钮、脉冲录音按钮、玻璃输入框。"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QLineEdit, QPushButton, QVBoxLayout, QWidget


GLOW_COLOR = QColor(0, 212, 255, 180)
PULSE_COLOR = QColor(255, 75, 92)


class GlowButton(QPushButton):
    """带 hover 发光扩散效果（box-shadow 的 Qt 等价物）的按钮。"""

    def __init__(self, text: str = "", primary: bool = False, parent=None) -> None:
        super().__init__(text, parent)
        if primary:
            self.setProperty("primary", True)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(GLOW_COLOR)
        self._glow.setBlurRadius(0)
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)
        self._anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def enterEvent(self, event) -> None:
        self._glow_animate(26)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._glow_animate(0)
        super().leaveEvent(event)

    def _glow_animate(self, target: int) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._glow.blurRadius())
        self._anim.setEndValue(target)
        self._anim.start()


class PulseButton(QWidget):
    """录音按钮：内嵌主按钮，录音时绘制红色脉冲光晕。"""

    def __init__(self, text: str = "开始录音", parent=None) -> None:
        super().__init__(parent)
        self._active = False
        self._pulse = 0.0
        self._btn = GlowButton(text, primary=True)
        self._btn.setProperty("recording", False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._btn)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1400)
        self._anim.valueChanged.connect(self._on_pulse)
        self._anim.finished.connect(self._restart_pulse)

    @property
    def button(self) -> QPushButton:
        return self._btn

    def set_active(self, active: bool) -> None:
        self._active = active
        self._btn.setProperty("recording", active)
        self._btn.style().unpolish(self._btn)
        self._btn.style().polish(self._btn)
        self._btn.setText("停止录音" if active else "开始录音")
        if active:
            self._anim.start()
        else:
            self._anim.stop()
            self._pulse = 0.0
        self.update()

    def _on_pulse(self, value: float) -> None:
        self._pulse = float(value)
        self.update()

    def _restart_pulse(self) -> None:
        if self._active:
            self._anim.start()

    def paintEvent(self, event) -> None:
        if not self._active:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = QPointF(self._btn.geometry().center())
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            t = (self._pulse - i * 0.22) % 1.0
            radius = 26 + t * 38
            color = QColor(PULSE_COLOR.red(), PULSE_COLOR.green(), PULSE_COLOR.blue(), int(150 * (1.0 - t)))
            painter.setBrush(color)
            painter.drawEllipse(center, radius, radius)
        super().paintEvent(event)


class GlassLineEdit(QLineEdit):
    """聚焦时产生发光边框效果的输入框。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        palette = self.palette()
        palette.setColor(self.palette().ColorRole.PlaceholderText, QColor(136, 136, 170))
        self.setPalette(palette)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(QColor(0, 212, 255, 120))
        self._glow.setBlurRadius(0)
        self._glow.setOffset(0, 0)
        self.setGraphicsEffect(self._glow)
        self._anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._anim.setDuration(160)

    def focusInEvent(self, event) -> None:
        self._glow_animate(18)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:
        self._glow_animate(0)
        super().focusOutEvent(event)

    def _glow_animate(self, target: int) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._glow.blurRadius())
        self._anim.setEndValue(target)
        self._anim.start()
