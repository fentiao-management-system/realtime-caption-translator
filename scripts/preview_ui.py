"""离屏渲染 UI 并保存预览截图，用于视觉验收（不启动真实窗口）。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.config import load_settings
from app.ui.theme import apply_theme
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setFont(QFont("Microsoft YaHei UI", 10))
    apply_theme(app)

    window = MainWindow(load_settings())
    window.resize(1280, 800)
    window.show()

    def populate() -> None:
        for i in range(6):
            speaker = "我" if i % 2 == 0 else "对方"
            window.subtitle_panel.add_subtitle(
                i,
                f"大家好，这是第 {i + 1} 句实时字幕演示文本。",
                f"12:0{i % 4}:{10 + i}",
                speaker,
            )
        window.subtitle_panel.set_translation(2, "This is the third demo subtitle line.")
        window.chat_panel.append_user("刚才我们讨论了什么？")
        window.chat_panel.show_typing()
        window.record_btn.set_active(True)
        window.subtitle_panel.set_live(True)

    QTimer.singleShot(60, populate)
    QTimer.singleShot(600, window.chat_panel.hide_typing)
    QTimer.singleShot(900, lambda: window.chat_panel.append_assistant("我们讨论了项目进度，决定下周完成第一版测试。"))
    QTimer.singleShot(
        1500,
        lambda: window.grab().save(str(Path(__file__).resolve().parent / "ui_preview.png")),
    )
    QTimer.singleShot(1700, app.quit)
    app.exec()
    print("preview saved")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
