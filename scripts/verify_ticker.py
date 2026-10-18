"""验证直播滚动字幕：卡片数量、滚动切换、停留逻辑、状态指示与像素。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PySide6.QtCore import QPoint, QRect, QTimer
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

    failed: list[str] = []

    def ok(condition: bool, name: str) -> None:
        print(("✅ PASS  " if condition else "❌ FAIL  ") + name)
        if not condition:
            failed.append(name)

    def step1() -> None:
        panel = window.subtitle_panel
        panel.add_subtitle(1, "大家好，这是第一条测试字幕", "12:00:01", "我")
        QTimer.singleShot(700, step2)  # 等待滑入动画结束

    def step2() -> None:
        panel = window.subtitle_panel
        panel.set_translation(1, "Hello everyone, this is the first test subtitle.")
        panel.add_subtitle(2, "这是第二条字幕内容", "12:00:05", "对方")
        QTimer.singleShot(700, step2b)  # 等待第二条滑入动画结束

    def step2b() -> None:
        panel = window.subtitle_panel
        ok(len(panel._cards) == 2, "最新 1-2 条：两卡片同时显示")
        ok(panel._cards[0]["entry"]["item_id"] == 1, "第一条升到顶部槽位")
        ok(panel._cards[1]["entry"]["item_id"] == 2, "第二条进入底部槽位")
        ok("第一条测试字幕" in panel._cards[0]["card"]._original.text(), "顶部卡片原文可见")
        ok("Hello" in panel._cards[0]["card"]._translation.text(), "顶部卡片译文已填充")
        ok("翻译中…" in panel._cards[1]["card"]._translation.text(), "底部卡片译文为占位（尚未到达）")
        QTimer.singleShot(700, step3)

    def step3() -> None:
        panel = window.subtitle_panel
        panel.add_subtitle(3, "第三条：排队等待滚动", "12:00:08", "对方")
        ok(len(panel._queue) == 1, "第三条进入排队（屏幕上仍只有 2 条）")
        ok(len(panel._cards) == 2, "排队期间卡片数不超 2")
        QTimer.singleShot(4200, step4)  # 3 秒停留 + 0.5 秒动画 + 余量

    def step4() -> None:
        panel = window.subtitle_panel
        ok(len(panel._queue) == 0, "停留 3 秒后自动切换，队列已消费")
        ok(len(panel._cards) == 2, "切换后仍为 2 条")
        ids = [item["entry"]["item_id"] for item in panel._cards]
        ok(2 in ids and 3 in ids, f"旧字幕上滑移出、新字幕滑入（当前: {ids}）")
        QTimer.singleShot(4200, step5)  # 无新字幕时，验证最后一条停留

    def step5() -> None:
        panel = window.subtitle_panel
        ok(len(panel._cards) == 2, "没有新字幕时，最后一条停留不消失")

        panel.set_live(True)
        ok("进行中" in panel._status_label.text(), "状态指示：进行中")
        panel.set_live(False)
        ok("待机" in panel._status_label.text(), "状态指示：待机")
        ok(bool(panel._clock_label.text().strip()), f"底部时钟显示: {panel._clock_label.text()}")

        panel.show_partial("临时字幕：正在说话中", "对方")
        QTimer.singleShot(200, step6)

    def step6() -> None:
        panel = window.subtitle_panel
        ok(panel._partial is not None, "临时字幕卡片已创建")
        ok("正在说话中" in panel._partial._text.text(), "临时字幕文本显示正确")
        panel.add_subtitle(99, "定稿字幕文本", "12:00:99", "我")
        QTimer.singleShot(200, step7)

    def step7() -> None:
        panel = window.subtitle_panel
        ok(panel._partial is None, "定稿后临时字幕被清除")
        speakers = [item["entry"].get("speaker", "") for item in panel._cards]
        ok(any(speakers), f"字幕卡片带说话人标记: {speakers}")

        panel.set_live(True)
        panel.set_translation(2, "This is the second subtitle.")
        QTimer.singleShot(200, pixel_check)

    def pixel_check() -> None:
        panel = window.subtitle_panel
        card = panel._cards[-1]["card"]
        top_left = card.mapTo(window, QPoint(0, 0))
        bottom_right = card.mapTo(window, QPoint(card.width(), card.height()))
        rect = QRect(top_left, bottom_right)
        img = window.grab().toImage()

        bg = img.pixelColor(rect.center().x(), rect.top() + 6)
        print(f"  卡片背景像素: ({bg.red()},{bg.green()},{bg.blue()}) 期望接近 (25,25,30) 玻璃色")
        ok(15 <= bg.red() <= 45 and 15 <= bg.green() <= 45 and 15 <= bg.blue() <= 55, "卡片为半透明玻璃背景")

        bright = 0
        for x in range(rect.left() + 20, rect.right() - 20, 2):
            for y in range(rect.top() + 10, rect.top() + 38, 2):
                c = img.pixelColor(x, y)
                if c.red() > 200 and c.green() > 200 and c.blue() > 200:
                    bright += 1
        ok(bright > 20, f"原文亮色文字像素: {bright}")

        gray = 0
        for x in range(rect.left() + 20, rect.right() - 20, 2):
            for y in range(rect.top() + 40, rect.bottom() - 8, 2):
                c = img.pixelColor(x, y)
                if 100 < c.red() < 170 and 100 < c.green() < 170 and c.blue() > c.red():
                    gray += 1
        ok(gray > 10, f"译文灰色文字像素: {gray}")

        window.grab().save(str(Path(__file__).resolve().parent / "ticker_preview.png"))
        print("截图已保存: scripts/ticker_preview.png")
        app.quit()

    QTimer.singleShot(80, step1)
    app.exec()

    if failed:
        print(f"\n共 {len(failed)} 项失败: {failed}")
        return 1
    print("\n字幕滚动验证全部通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
