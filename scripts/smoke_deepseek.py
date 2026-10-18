"""验证 DeepSeek API Key 与翻译/问答链路。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.client import DeepSeekClient
from app.config import load_settings


def main() -> int:
    settings = load_settings()
    client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    print("翻译测试：")
    print("  ", client.translate("今天天气不错，我们一起去公园散步吧。"))
    print("问答测试：")
    print("  ", client.chat([{"role": "user", "content": "用一句话回答：1+1 等于几？"}]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
