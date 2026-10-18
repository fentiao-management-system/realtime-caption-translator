"""深色玻璃态主题：颜色常量 + 全局 QSS + 气泡样式。"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette


BG = "#0a0a0f"
TEXT = "#f0f0f5"
TEXT_SECONDARY = "#8888aa"
GLASS_BG = "rgba(255,255,255,13)"
GLASS_BORDER = "rgba(255,255,255,20)"
GRADIENT_A = "#00d4ff"
GRADIENT_B = "#00ff87"
DANGER_A = "#ff4b5c"
DANGER_B = "#ff6a88"

USER_BUBBLE_QSS = (
    "background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1a6dff, stop:1 #00c6ff);"
    "color: #ffffff; border-radius: 12px; padding: 10px 14px;"
)
AI_BUBBLE_QSS = (
    "background: rgba(255,255,255,13); border: 1px solid rgba(255,255,255,20);"
    "color: #f0f0f5; border-radius: 12px; padding: 10px 14px;"
)

QUICK_QUESTIONS = ["刚才讨论了什么？", "总结一下要点", "下一步的建议？"]


def apply_dark_palette(app) -> None:
    """设置深色调色板，避免未样式化控件（滚动区、弹窗等）退回白底。"""
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0a0a0f"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f0f5"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#14141d"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1a1a24"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f0f0f5"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1a1a24"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f0f0f5"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#14141d"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f0f0f5"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8888aa"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#00d4ff"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0a0a0f"))
    app.setPalette(palette)


def apply_theme(app) -> None:
    """一次性应用深色调色板 + 全局样式表。"""
    apply_dark_palette(app)
    app.setStyleSheet(build_qss())


def build_qss() -> str:
    """生成全局样式表（纯字符串，无插值）。"""
    return """
QMainWindow {
    background-color: #0a0a0f;
    color: #f0f0f5;
}

/* ---- 玻璃卡片 ---- */
#GlassCard {
    background-color: rgba(255,255,255,13);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 16px;
}

/* ---- 标签 ---- */
QLabel#PanelTitle {
    color: #f0f0f5;
    font-size: 16px;
    font-weight: 700;
}
QLabel#SectionTitle {
    color: #8888aa;
    font-size: 12px;
    font-weight: 600;
}
QLabel#SectionLabel, QLabel#MutedLabel {
    color: #8888aa;
    font-size: 12px;
}

/* ---- 按钮 ---- */
QPushButton {
    background-color: rgba(255,255,255,10);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 12px;
    color: #f0f0f5;
    padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: rgba(255,255,255,18);
    border-color: rgba(0,212,255,120);
}
QPushButton:pressed {
    background-color: rgba(255,255,255,8);
    padding-top: 9px;
    padding-bottom: 7px;
}
QPushButton[primary="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00d4ff, stop:1 #00ff87);
    border: none;
    color: #081018;
}
QPushButton[primary="true"]:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #33ddff, stop:1 #33ffa8);
}
QPushButton[primary="true"]:pressed {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00bde6, stop:1 #00e678);
    padding-top: 9px;
    padding-bottom: 7px;
}
QPushButton[recording="true"] {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff4b5c, stop:1 #ff6a88);
    color: #ffffff;
}
QPushButton:disabled {
    color: rgba(255,255,255,60);
    background-color: rgba(255,255,255,8);
}
QPushButton#TagButton {
    background-color: rgba(255,255,255,10);
    border: 1px solid rgba(255,255,255,18);
    border-radius: 12px;
    color: #aab;
    padding: 5px 10px;
    font-size: 12px;
    font-weight: 400;
}
QPushButton#TagButton:hover {
    border-color: #00d4ff;
    color: #f0f0f5;
    background-color: rgba(0,212,255,14);
}

/* ---- 下拉选择器 ---- */
QComboBox {
    background-color: rgba(255,255,255,10);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 10px;
    padding: 7px 12px;
    color: #f0f0f5;
}
QComboBox:hover {
    border-color: rgba(0,212,255,110);
}
QComboBox::drop-down {
    border: none;
    width: 26px;
}
QComboBox::down-arrow {
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #8888aa;
    margin-right: 6px;
}
QComboBox QAbstractItemView {
    background-color: #14141d;
    border: 1px solid rgba(255,255,255,20);
    border-radius: 10px;
    selection-background-color: rgba(0,212,255,45);
    outline: 0;
    padding: 4px;
}
QComboBox QAbstractItemView::item {
    padding: 7px 10px;
    color: #f0f0f5;
    border-radius: 6px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: rgba(0,212,255,22);
}

/* ---- 滑块 ---- */
QSlider::groove:horizontal {
    height: 4px;
    background: rgba(255,255,255,20);
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00d4ff, stop:1 #00ff87);
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
    background: #f0f0f5;
    border: 2px solid rgba(0,212,255,130);
}
QSlider::handle:horizontal:hover {
    border-color: #00d4ff;
}

/* ---- 输入框 ---- */
QLineEdit {
    background-color: rgba(255,255,255,13);
    border: 1px solid rgba(255,255,255,20);
    border-radius: 12px;
    padding: 9px 14px;
    color: #f0f0f5;
    selection-background-color: rgba(0,212,255,90);
}
QLineEdit:focus {
    border: 1px solid #00d4ff;
    background-color: rgba(0,212,255,8);
}

/* ---- 滚动条 ---- */
QScrollBar:vertical {
    width: 4px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(255,255,255,35);
    border-radius: 2px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255,255,255,70);
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: none;
}
QScrollBar:horizontal {
    height: 4px;
    background: transparent;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: rgba(255,255,255,35);
    border-radius: 2px;
    min-width: 30px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255,255,255,70);
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: none;
}

/* ---- 列表 / 滚动区域 ---- */
QListWidget {
    background: transparent;
    border: none;
    outline: 0;
}
QListWidget::item {
    border-bottom: 1px solid rgba(255,255,255,8);
    padding: 8px 6px;
    color: #f0f0f5;
    border-radius: 8px;
}
QListWidget::item:hover {
    background-color: rgba(255,255,255,6);
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}
QWidget#RootPanel {
    background: transparent;
}
QMessageBox {
    background-color: #14141d;
}
QMessageBox QLabel {
    color: #f0f0f5;
}

/* ---- 状态栏 / 提示 ---- */
QStatusBar {
    background: rgba(255,255,255,6);
    color: #8888aa;
    border-top: 1px solid rgba(255,255,255,10);
}
QToolTip {
    background-color: #14141d;
    color: #f0f0f5;
    border: 1px solid rgba(255,255,255,20);
    padding: 4px 8px;
}
QSplitter::handle {
    background: transparent;
}
"""
