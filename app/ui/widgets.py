from __future__ import annotations

import datetime

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPoint, QPropertyAnimation, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .bubbles import BubbleChat
from .controls import GlassLineEdit, GlowButton
from .theme import QUICK_QUESTIONS


SPEAKER_COLORS = {"我": "#00d4ff", "对方": "#c084fc"}


def _speaker_color(speaker: str) -> str:
    return SPEAKER_COLORS.get(speaker, "#8888aa")


def _elide(text: str, font: QFont, max_width: int) -> str:
    if max_width <= 0:
        return text
    return QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, max_width)


class _SubtitleCard(QWidget):
    """单条直播字幕卡片：说话人 + 原文（大号亮色）+ 译文（小号灰色）。"""

    HEIGHT = 72

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(
            "background: rgba(255,255,255,15);"
            "border: 1px solid rgba(255,255,255,15);"
            "border-radius: 12px;"
        )
        self._original_font = QFont("Microsoft YaHei UI", 20)
        self._original_font.setWeight(QFont.Weight.DemiBold)
        self._translation_font = QFont("Microsoft YaHei UI", 14)

        self._speaker = QLabel("")
        self._speaker.setStyleSheet(
            "color: #8888aa; font-size: 12px; font-weight: 600;"
            "background: transparent; border: none;"
        )
        self._original = QLabel("")
        self._original.setStyleSheet(
            "color: #f0f0f5; font-size: 20px; font-weight: 600; background: transparent; border: none;"
        )
        original_row = QHBoxLayout()
        original_row.setContentsMargins(0, 0, 0, 0)
        original_row.setSpacing(8)
        original_row.addWidget(self._original, 1)
        original_row.addWidget(self._speaker, 0, Qt.AlignmentFlag.AlignRight)

        self._translation = QLabel("")
        self._translation.setStyleSheet(
            "color: #8888aa; font-size: 14px; background: transparent; border: none;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(4)
        layout.addLayout(original_row)
        layout.addWidget(self._translation)
        self.setFixedHeight(self.HEIGHT)

    def set_content(
        self,
        original: str,
        translation: str | None,
        max_width: int,
        speaker: str = "",
    ) -> None:
        self._speaker.setText(speaker)
        self._speaker.setStyleSheet(
            f"color: {_speaker_color(speaker)}; font-size: 12px; font-weight: 600;"
            "background: transparent; border: none;"
        )
        self._original.setText(_elide(original, self._original_font, max_width))
        self._translation.setText(
            _elide(translation, self._translation_font, max_width)
            if translation
            else "翻译中…"
        )


class _PartialCard(QWidget):
    """临时字幕行：说话过程中的灰色预览文字。"""

    HEIGHT = 40

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._font = QFont("Microsoft YaHei UI", 15)
        self._speaker = QLabel("")
        self._speaker.setStyleSheet(
            "color: #8888aa; font-size: 12px; background: transparent; border: none;"
        )
        self._text = QLabel("")
        self._text.setStyleSheet(
            "color: #6e6e93; font-size: 15px; background: transparent; border: none;"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 0, 20, 0)
        row.setSpacing(8)
        row.addWidget(self._text, 1)
        row.addWidget(self._speaker, 0, Qt.AlignmentFlag.AlignRight)
        self.setFixedHeight(self.HEIGHT)

    def set_content(self, text: str, speaker: str, max_width: int) -> None:
        self._speaker.setText(speaker)
        self._speaker.setStyleSheet(
            f"color: {_speaker_color(speaker)}; font-size: 12px; background: transparent; border: none;"
        )
        self._text.setText(_elide(text, self._font, max_width))


class SubtitlePanel(QWidget):
    """直播滚动字幕：最新 1-2 条 + 灰色临时字幕行，旧字幕上滑消失。"""

    CARD_HEIGHT = _SubtitleCard.HEIGHT
    CARD_GAP = 8
    SLOT_TOP = 8
    SLOT_BOTTOM = SLOT_TOP + CARD_HEIGHT + CARD_GAP
    TEMP_Y = SLOT_BOTTOM + CARD_HEIGHT + CARD_GAP
    ANIM_MS = 500
    DWELL_MS = 3000

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("SubtitlePanel")
        self._cards: list[dict] = []  # [顶部卡片, 底部卡片]
        self._queue: list[dict] = []
        self._entries: dict[int, dict] = {}
        self._animating = False
        self._partial: _PartialCard | None = None

        header = QHBoxLayout()
        title = QLabel("实时字幕")
        title.setObjectName("PanelTitle")
        header.addWidget(title)
        header.addStretch(1)

        self._stage = QWidget()
        self._stage.setMinimumHeight(self.TEMP_Y + _PartialCard.HEIGHT + self.SLOT_TOP)

        footer = QHBoxLayout()
        self._status_label = QLabel("实时字幕 ● 待机")
        self._status_label.setObjectName("SectionLabel")
        self._clock_label = QLabel("")
        self._clock_label.setObjectName("SectionLabel")
        footer.addStretch(1)
        footer.addWidget(self._status_label)
        footer.addSpacing(12)
        footer.addWidget(self._clock_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._stage, 1)
        layout.addLayout(footer)

        self._dwell_timer = QTimer(self)
        self._dwell_timer.setSingleShot(True)
        self._dwell_timer.setInterval(self.DWELL_MS)
        self._dwell_timer.timeout.connect(self._on_dwell)

        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(1000)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start()
        self._update_clock()

    # ---------- 对外接口（MainWindow / 控制器使用） ----------

    def add_subtitle(self, item_id: int, text: str, timestamp: str, speaker: str = "") -> None:
        self._clear_partial()
        entry = {"item_id": item_id, "text": text, "translation": None, "speaker": speaker}
        self._entries[item_id] = entry
        self._enqueue_or_show(entry)

    def show_partial(self, text: str, speaker: str = "") -> None:
        if self._partial is None:
            self._partial = _PartialCard(self._stage)
            self._partial.setGeometry(0, self.TEMP_Y, self._card_width(), _PartialCard.HEIGHT)
            self._partial.show()
        self._partial.set_content(text, speaker, self._card_width() - 40)

    def set_translation(self, item_id: int, translation: str) -> None:
        entry = self._entries.get(item_id)
        if entry is not None:
            entry["translation"] = translation
        for item in self._cards:
            if item["entry"]["item_id"] == item_id:
                item["card"].set_content(
                    entry["text"],
                    translation,
                    self._card_width() - 40,
                    entry.get("speaker", ""),
                )
                break

    def set_live(self, live: bool) -> None:
        color = "#ff4b5c" if live else "#8888aa"
        state = "进行中" if live else "待机"
        self._status_label.setText(
            f'实时字幕 <span style="color:{color};">●</span> {state}'
        )

    def clear_all(self) -> None:
        self._dwell_timer.stop()
        self._queue.clear()
        self._entries.clear()
        self._clear_partial()
        for item in self._cards:
            item["card"].deleteLater()
        self._cards.clear()

    # ---------- 状态机 ----------

    def _clear_partial(self) -> None:
        if self._partial is not None:
            self._partial.deleteLater()
            self._partial = None

    def _enqueue_or_show(self, entry: dict) -> None:
        if self._animating or len(self._cards) >= 2:
            self._queue.append(entry)
            if not self._animating and len(self._cards) >= 2 and not self._dwell_timer.isActive():
                self._start_shift()
            return
        self._start_shift(entry)

    def _on_dwell(self) -> None:
        if self._animating:
            return
        if self._queue:
            self._start_shift()

    def _start_shift(self, entry: dict | None = None) -> None:
        if self._animating:
            return
        if entry is None:
            if not self._queue:
                return
            entry = self._queue.pop(0)

        self._animating = True
        self._dwell_timer.stop()

        group = QParallelAnimationGroup(self)
        top_card = self._cards[0] if len(self._cards) >= 2 else None
        bottom_card = self._cards[-1] if self._cards else None

        if top_card is not None:
            group.addAnimation(
                self._anim_pos(top_card["card"], self.SLOT_TOP - (self.CARD_HEIGHT + self.CARD_GAP))
            )
            group.addAnimation(self._anim_opacity(top_card["card"], 0.0))
        if bottom_card is not None:
            group.addAnimation(self._anim_pos(bottom_card["card"], self.SLOT_TOP))

        new_card = self._make_card(entry)
        group.addAnimation(self._anim_pos(new_card, self.SLOT_BOTTOM))
        group.addAnimation(self._anim_opacity(new_card, 1.0))

        survivors = ([bottom_card] if bottom_card is not None else []) + [
            {"card": new_card, "entry": entry}
        ]
        group.finished.connect(lambda: self._after_shift(survivors, top_card))
        group.start(QParallelAnimationGroup.DeletionPolicy.DeleteWhenStopped)

    def _after_shift(self, survivors: list[dict], top_card: dict | None) -> None:
        if top_card is not None:
            top_card["card"].deleteLater()
        self._cards = survivors
        self._animating = False
        self._start_dwell()
        self._process_queue()

    def _process_queue(self) -> None:
        if self._animating or not self._queue:
            return
        if len(self._cards) < 2:
            self._start_shift()

    def _start_dwell(self) -> None:
        self._dwell_timer.stop()
        self._dwell_timer.start()

    # ---------- 卡片与动画 ----------

    def _make_card(self, entry: dict) -> QWidget:
        card = _SubtitleCard(self._stage)
        card.resize(self._card_width(), self.CARD_HEIGHT)
        card.move(0, max(self._stage.height(), self.SLOT_BOTTOM + self.CARD_HEIGHT + self.CARD_GAP))
        card.set_content(
            entry["text"],
            entry["translation"],
            self._card_width() - 40,
            entry.get("speaker", ""),
        )
        card.show()
        effect = QGraphicsOpacityEffect(card)
        effect.setOpacity(0.0)
        card.setGraphicsEffect(effect)
        return card

    def _anim_pos(self, widget: QWidget, target_y: int) -> QPropertyAnimation:
        anim = QPropertyAnimation(widget, b"pos", self)
        anim.setDuration(self.ANIM_MS)
        anim.setStartValue(widget.pos())
        anim.setEndValue(QPoint(0, target_y))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    def _anim_opacity(self, widget: QWidget, target: float) -> QPropertyAnimation:
        effect = widget.graphicsEffect()
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(self.ANIM_MS)
        anim.setStartValue(effect.opacity() if effect is not None else 1.0)
        anim.setEndValue(target)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    def _card_width(self) -> int:
        return max(1, self._stage.width())

    def _update_clock(self) -> None:
        self._clock_label.setText(datetime.datetime.now().strftime("%H:%M:%S"))

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        width = self._card_width()
        for item in self._cards:
            item["card"].resize(width, self.CARD_HEIGHT)
            item["card"].set_content(
                item["entry"]["text"],
                item["entry"]["translation"],
                width - 40,
                item["entry"].get("speaker", ""),
            )
        if self._partial is not None:
            self._partial.setGeometry(0, self.TEMP_Y, width, _PartialCard.HEIGHT)


class ChatPanel(QWidget):
    """AI 问答面板：气泡列表 + 快捷问题标签 + 底部输入框。"""

    send_requested = Signal(str)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ChatPanel")

        header = QHBoxLayout()
        title = QLabel("AI 问答")
        title.setObjectName("PanelTitle")
        clear_btn = QPushButton("清空上下文")
        clear_btn.setFixedWidth(90)
        clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear_clicked)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(clear_btn)

        self.chat = BubbleChat()

        tag_row = QHBoxLayout()
        tag_row.setSpacing(6)
        for question in QUICK_QUESTIONS:
            tag = QPushButton(question)
            tag.setObjectName("TagButton")
            tag.setCursor(Qt.CursorShape.PointingHandCursor)
            tag.clicked.connect(lambda checked=False, q=question: self._send(q))
            tag_row.addWidget(tag)
        tag_row.addStretch(1)

        self.input = GlassLineEdit()
        self.input.setPlaceholderText("输入你的问题，回车发送…")
        self._input_wrap = QWidget()
        wrap_layout = QHBoxLayout(self._input_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.addWidget(self.input)

        self.send_btn = GlowButton("发送", primary=True)
        self.send_btn.setFixedWidth(70)
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(lambda: self._send(self.input.text()))
        self.input.returnPressed.connect(lambda: self._send(self.input.text()))

        input_row = QHBoxLayout()
        input_row.addWidget(self._input_wrap, 1)
        input_row.addWidget(self.send_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addLayout(tag_row)
        layout.addWidget(self.chat, 1)
        layout.addLayout(input_row)

    # ---------- 对外接口（MainWindow / 控制器使用） ----------

    def append_user(self, question: str) -> None:
        self.chat.append_user(question)

    def append_assistant(self, answer: str) -> None:
        self.chat.append_assistant(answer)

    def show_typing(self) -> None:
        self.chat.show_typing()

    def hide_typing(self) -> None:
        self.chat.hide_typing()

    def clear_history(self) -> None:
        self.chat.clear()

    # ---------- 内部 ----------

    def _on_clear_clicked(self) -> None:
        self.clear_history()
        self.clear_requested.emit()

    def _send(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.send_requested.emit(text)
        self._animate_input_clear()

    def _animate_input_clear(self) -> None:
        """输入框淡出 → 清空 → 淡入。"""
        wrap = self._input_wrap
        effect = QGraphicsOpacityEffect(wrap)
        wrap.setGraphicsEffect(effect)

        fade_out = QPropertyAnimation(effect, b"opacity", wrap)
        fade_out.setDuration(110)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.Type.InQuad)

        def finish() -> None:
            self.input.clear()
            fade_in = QPropertyAnimation(effect, b"opacity", wrap)
            fade_in.setDuration(160)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)
            fade_in.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

        fade_out.finished.connect(finish)
        fade_out.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
