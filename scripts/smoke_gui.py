"""离屏启动 GUI，验证界面代码无错误。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.config import load_settings
from app.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow(load_settings())
    window.show()
    QTimer.singleShot(1500, app.quit)
    app.exec()
    print("GUI 启动验证通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
