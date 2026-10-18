"""气泡聊天：用户/AI 消息气泡、打字指示器、消息上浮动画。"""

from __future__ import annotations

import math

from PySide6.QtCore import QEasingCurve, QPoint, QPointF, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .theme import AI_BUBBLE_QSS, USER_BUBBLE_QSS


class TypingIndicator(QWidget):
    """"正在输入..." 跳动小点动画。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedSize(64, 34)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.06) % 1.0
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            t = (self._phase - i * 0.22) % 1.0
            wave = max(0.0, math.sin(math.pi * t))
            color = QColor(240, 240, 245, int(90 + 165 * wave))
            painter.setBrush(color)
            radius = 4.0 + 1.6 * wave
            painter.drawEllipse(QPointF(14 + i * 18, self.height() / 2.0), radius, radius)


class BubbleChat(QScrollArea):
    """消息气泡列表，支持上浮淡入动画与打字指示器。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)

        self._container = QWidget()
        self._container.setAutoFillBackground(False)
        self._container.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(10)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)

        self._typing_row: QWidget | None = None
        self._typing: TypingIndicator | None = None

    def append_user(self, text: str) -> None:
        self._add_bubble(text, user=True)

    def append_assistant(self, text: str) -> None:
        self._add_bubble(text, user=False)

    def show_typing(self) -> None:
        if self._typing is not None:
            return
        self._typing = TypingIndicator()
        self._typing.setStyleSheet(AI_BUBBLE_QSS)
        self._typing_row = self._make_row(self._typing, user=False)
        self._layout.addWidget(self._typing_row)
        self._scroll_to_bottom()

    def hide_typing(self) -> None:
        if self._typing is None:
            return
        self._typing.stop()
        self._typing = None
        if self._typing_row is not None:
            self._layout.removeWidget(self._typing_row)
            self._typing_row.deleteLater()
            self._typing_row = None

    def clear(self) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._typing = None
        self._typing_row = None

    def _add_bubble(self, text: str, user: bool) -> None:
        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        bubble.setStyleSheet(USER_BUBBLE_QSS if user else AI_BUBBLE_QSS)
        bubble.setMaximumWidth(max(180, int(self.viewport().width() * 0.78)))

        row = self._make_row(bubble, user=user)
        self._layout.addWidget(row)

        effect = QGraphicsOpacityEffect(bubble)
        bubble.setGraphicsEffect(effect)
        fade = QPropertyAnimation(effect, b"opacity", bubble)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        fade.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        self._scroll_to_bottom()
        QTimer.singleShot(0, lambda: self._slide_up(row))

    def _slide_up(self, row: QWidget) -> None:
        start = row.pos()
        slide = QPropertyAnimation(row, b"pos", row)
        slide.setDuration(220)
        slide.setStartValue(start + QPoint(0, 10))
        slide.setEndValue(start)
        slide.setEasingCurve(QEasingCurve.Type.OutCubic)
        slide.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    @staticmethod
    def _make_row(widget: QWidget, user: bool) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        if user:
            layout.addStretch(1)
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight)
        else:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft)
            layout.addStretch(1)
        return row

    def _scroll_to_bottom(self) -> None:
        QTimer.singleShot(
            0,
            lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()),
        )
