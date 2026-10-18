"""程序化 UI 验证：布局尺寸 + 关键像素颜色（离屏渲染）。"""

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

    def check() -> None:
        central = window.centralWidget()
        layout = central.layout()
        left = layout.itemAt(0).widget()
        center = layout.itemAt(1).widget()
        right = layout.itemAt(2).widget()

        print(f"左栏宽: {left.width()} (期望 240)")
        print(f"右栏宽: {right.width()} (期望 340)")
        print(f"中栏宽: {center.width()} (弹性)")

        window.subtitle_panel.add_subtitle(0, "测试字幕文本", "12:00:00")
        window.chat_panel.append_user("测试问题")
        window.chat_panel.show_typing()
        QTimer.singleShot(250, sample_pixels)

    def sample_pixels() -> None:
        img = window.grab().toImage()

        def px(x: int, y: int) -> tuple:
            c = img.pixelColor(x, y)
            return (c.red(), c.green(), c.blue())

        bg = px(5, 400)
        print(f"窗口背景(5,400): {bg} (期望接近 #0a0a0f)")

        btn_center = window.record_btn.button.mapTo(window, window.record_btn.button.rect().center())
        print(f"录音按钮中心: {px(btn_center.x(), btn_center.y())} (期望青绿渐变)")

        blue = 0
        for x in range(img.width() - 340, img.width(), 2):
            for y in range(0, img.height(), 2):
                r, g, b = px(x, y)
                if b > 180 and r < 120 and 100 < g < 230:
                    blue += 1
        print(f"问答区蓝色(用户气泡)像素数: {blue} (期望 > 100)")

        app.quit()

    QTimer.singleShot(80, check)
    app.exec()
    print("UI 验证完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
