"""列出音频设备，验证麦克风与系统声音回环设备可用。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.audio.capture import discover_devices


def main() -> int:
    devices = discover_devices()
    print("== 麦克风设备 ==")
    for info in devices["mic"]:
        marker = " ← 默认" if info["index"] == devices["default_mic"] else ""
        print(f"  [{info['index']}] {info['name']}{marker}")
    print("== 系统声音（回环）设备 ==")
    for info in devices["loopback"]:
        marker = " ← 默认" if info["index"] == devices["default_loopback"] else ""
        print(f"  [{info['index']}] {info['name']}{marker}")
    if not devices["loopback"]:
        print("  （未检测到回环设备：录音时将只有麦克风）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
