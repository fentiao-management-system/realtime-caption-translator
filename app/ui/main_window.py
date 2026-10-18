from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from ..audio.capture import discover_devices
from ..config import Settings
from ..controller import AppController
from .controls import GlowButton, PulseButton
from .widgets import ChatPanel, SubtitlePanel


def _glass(widget: QWidget) -> QWidget:
    """让普通 QWidget 应用玻璃卡片背景。"""
    widget.setObjectName("GlassCard")
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return widget


class MainWindow(QMainWindow):
    """三栏式主窗口：左控制栏 / 中实时字幕 / 右 AI 问答。"""

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.controller = AppController(settings)
        self._running = False
        self._mic_devices: list[dict] = []
        self._sys_devices: list[dict] = []

        self.setWindowTitle("实时对话记录 · 字幕翻译 · AI 问答")
        self.resize(1280, 800)
        self.setMinimumSize(980, 640)

        self._build_ui()
        self._connect_signals()
        self._populate_devices()

        self.statusBar().showMessage(
            f"DeepSeek 模型：{settings.deepseek_model} ｜ 识别模型：{settings.asr_model}"
        )

    # ---------- UI 构建 ----------

    def _build_ui(self) -> None:
        left = self._build_left_panel()
        center = self._build_center_panel()
        self.chat_panel = ChatPanel()
        self.chat_panel.setObjectName("GlassCard")
        self.chat_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.chat_panel.setFixedWidth(340)

        central = QWidget()
        central.setObjectName("RootPanel")
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)
        layout.addWidget(left)
        layout.addWidget(center, 1)
        layout.addWidget(self.chat_panel)
        self.setCentralWidget(central)

    def _build_left_panel(self) -> QWidget:
        panel = _glass(QWidget())
        panel.setFixedWidth(240)

        title = QLabel("实时对话记录")
        title.setObjectName("PanelTitle")
        subtitle = QLabel("字幕翻译 · AI 问答")
        subtitle.setObjectName("SectionLabel")

        self.record_btn = PulseButton()

        mic_label = QLabel("音频设备")
        mic_label.setObjectName("SectionTitle")
        mic_caption = QLabel("麦克风")
        mic_caption.setObjectName("SectionLabel")
        self.mic_combo = QComboBox()
        sys_caption = QLabel("系统声音")
        sys_caption.setObjectName("SectionLabel")
        self.sys_combo = QComboBox()

        vol_label = QLabel("音量")
        vol_label.setObjectName("SectionTitle")
        mic_vol_caption = QLabel("麦克风音量")
        mic_vol_caption.setObjectName("SectionLabel")
        self.mic_volume = QSlider(Qt.Orientation.Horizontal)
        self.mic_volume.setRange(0, 150)
        self.mic_volume.setValue(int(self.settings.mic_volume * 100))
        sys_vol_caption = QLabel("系统音量")
        sys_vol_caption.setObjectName("SectionLabel")
        self.sys_volume = QSlider(Qt.Orientation.Horizontal)
        self.sys_volume.setRange(0, 150)
        self.sys_volume.setValue(int(self.settings.sys_volume * 100))

        model_label = QLabel("模型")
        model_label.setObjectName("SectionTitle")
        model_info = QLabel(f"ASR: {self.settings.asr_model}\nLLM: {self.settings.deepseek_model}")
        model_info.setObjectName("MutedLabel")
        model_info.setWordWrap(True)

        self.open_btn = GlowButton("打开记录")
        self.open_btn.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(8)
        layout.addWidget(self.record_btn)
        layout.addSpacing(12)
        layout.addWidget(mic_label)
        layout.addWidget(mic_caption)
        layout.addWidget(self.mic_combo)
        layout.addWidget(sys_caption)
        layout.addWidget(self.sys_combo)
        layout.addSpacing(12)
        layout.addWidget(vol_label)
        layout.addWidget(mic_vol_caption)
        layout.addWidget(self.mic_volume)
        layout.addWidget(sys_vol_caption)
        layout.addWidget(self.sys_volume)
        layout.addSpacing(12)
        layout.addWidget(model_label)
        layout.addWidget(model_info)
        layout.addStretch(1)
        layout.addWidget(self.open_btn)
        return panel

    def _build_center_panel(self) -> QWidget:
        panel = _glass(QWidget())
        self.subtitle_panel = SubtitlePanel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.subtitle_panel, 1)
        return panel

    def _connect_signals(self) -> None:
        self.record_btn.button.clicked.connect(self._toggle_recording)
        self.open_btn.clicked.connect(self._open_session_dir)
        self.chat_panel.send_requested.connect(self._on_ask)
        self.chat_panel.clear_requested.connect(self.controller.clear_memory)

        self.controller.status_changed.connect(self._set_status)
        self.controller.error_occurred.connect(self._on_error)
        self.controller.subtitle_added.connect(self.subtitle_panel.add_subtitle)
        self.controller.partial_text.connect(self.subtitle_panel.show_partial)
        self.controller.translation_ready.connect(self.subtitle_panel.set_translation)
        self.controller.answer_ready.connect(self._on_answer)

    # ---------- 设备 ----------

    def _populate_devices(self) -> None:
        try:
            devices = discover_devices()
        except Exception as exc:
            self._on_error(f"音频设备枚举失败：{exc}")
            return

        self._mic_devices = devices["mic"]
        self._sys_devices = devices["loopback"]

        for info in self._mic_devices:
            self.mic_combo.addItem(str(info["name"]), int(info["index"]))
        for info in self._sys_devices:
            self.sys_combo.addItem(str(info["name"]), int(info["index"]))

        self._select_by_index(self.mic_combo, self._mic_devices, devices["default_mic"])
        self._select_by_index(self.sys_combo, self._sys_devices, devices["default_loopback"])

        if not self._sys_devices:
            self._set_status("未检测到系统声音回环设备，仅使用麦克风（可后续在声卡驱动/设置中开启）")

    @staticmethod
    def _select_by_index(combo: QComboBox, devices: list[dict], device_index: Optional[int]) -> None:
        if device_index is None:
            return
        for row, info in enumerate(devices):
            if int(info["index"]) == device_index:
                combo.setCurrentIndex(row)
                return

    def _selected_device(self, combo: QComboBox, devices: list[dict]) -> Optional[dict]:
        row = combo.currentIndex()
        if 0 <= row < len(devices):
            return devices[row]
        return None

    # ---------- 动作 ----------

    def _toggle_recording(self) -> None:
        if not self._running:
            mic = self._selected_device(self.mic_combo, self._mic_devices)
            sys_dev = self._selected_device(self.sys_combo, self._sys_devices)
            if mic is None and sys_dev is None:
                QMessageBox.warning(self, "没有输入设备", "请先选择至少一个音频输入设备。")
                return
            self.controller.start_recording(
                mic_info=mic,
                sys_info=sys_dev,
                mic_volume=self.mic_volume.value() / 100.0,
                sys_volume=self.sys_volume.value() / 100.0,
            )
            self._running = True
            self.record_btn.set_active(True)
            self.subtitle_panel.set_live(True)
        else:
            self.controller.stop_recording()
            self._running = False
            self.record_btn.set_active(False)
            self.subtitle_panel.set_live(False)

    def _on_ask(self, question: str) -> None:
        self.chat_panel.append_user(question)
        self.chat_panel.show_typing()
        self._set_status("AI 思考中…")
        self.controller.ask(question)

    def _on_answer(self, question: str, answer: str) -> None:
        self.chat_panel.hide_typing()
        self.chat_panel.append_assistant(answer)
        self._set_status("AI 回答完成")

    def _open_session_dir(self) -> None:
        path = Path(self.settings.session_dir)
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(path))  # Windows
        except AttributeError:
            subprocess.Popen(["explorer", str(path)])

    def _set_status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_error(self, message: str) -> None:
        self.chat_panel.hide_typing()
        self.statusBar().showMessage(message)
        QMessageBox.warning(self, "提示", message)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.controller.shutdown()
        super().closeEvent(event)
