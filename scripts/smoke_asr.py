"""验证 faster-whisper 模型可加载并可转写（首次运行会下载模型）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time

import numpy as np

from app.config import load_settings


def main() -> int:
    settings = load_settings()
    print(f"加载语音识别模型：{settings.asr_model}（首次运行会下载，请耐心等待）…")
    started = time.perf_counter()

    from faster_whisper import WhisperModel

    model = WhisperModel(settings.asr_model, device=settings.asr_device, compute_type=settings.asr_compute_type)
    print(f"模型加载完成，耗时 {time.perf_counter() - started:.1f}s")

    # 静音输入应当不产生文本（验证管线不报错）
    segments, _ = model.transcribe(
        np.zeros(16000, dtype=np.float32) / 32768.0,
        language=settings.asr_language,
        beam_size=1,
        vad_filter=True,
    )
    text = "".join(seg.text for seg in segments).strip()
    print(f"静音转写结果：{text!r}（应为空）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
