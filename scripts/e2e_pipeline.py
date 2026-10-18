"""端到端验证：合成中文语音 → 分段 → 识别 → DeepSeek 翻译。

需要已安装 edge-tts（仅用于生成测试音频）。
"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np

from app.ai.client import DeepSeekClient
from app.audio.segmenter import Segmenter
from app.config import load_settings


def synthesize(sentence: str, out_path: Path) -> Path:
    import asyncio

    import edge_tts

    async def _run() -> None:
        communicate = edge_tts.Communicate(sentence, "zh-CN-XiaoxiaoNeural")
        await communicate.save(str(out_path))

    asyncio.run(_run())
    return out_path


def load_audio_16k(path: Path) -> np.ndarray:
    """用 PyAV 把任意音频（mp3/wav）解码为 16k 单声道 int16。"""
    import av

    container = av.open(str(path))
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    chunks: list[np.ndarray] = []
    for frame in container.decode(audio=0):
        for out_frame in resampler.resample(frame):
            chunks.append(out_frame.to_ndarray()[0])
    for out_frame in resampler.resample(None):
        chunks.append(out_frame.to_ndarray()[0])
    if not chunks:
        raise RuntimeError("音频解码结果为空")
    return np.concatenate(chunks).astype(np.int16)


def main() -> int:
    settings = load_settings()
    sentence = "大家好，今天我们讨论一下项目进度，下周要完成第一版测试。"
    wav_path = Path(__file__).resolve().parent / "test_speech.wav"
    mp3_path = Path(__file__).resolve().parent / "test_speech.mp3"
    audio_path = wav_path if wav_path.exists() else mp3_path

    if audio_path.exists():
        print("1) 复用已存在的测试音频…")
    else:
        print("1) 合成中文语音…")
        synthesize(sentence, mp3_path)
        audio_path = mp3_path
    audio = load_audio_16k(audio_path)
    print(f"   音频时长 {len(audio) / settings.sample_rate:.1f}s")

    print("2) 语音分段…")
    segmenter = Segmenter(sample_rate=settings.sample_rate, energy_threshold=settings.energy_threshold)
    segments = segmenter.feed(audio) + segmenter.flush()
    print(f"   得到 {len(segments)} 个语音段")

    print("3) 语音识别（faster-whisper）…")
    from app.asr.transcriber import Transcriber

    results: list[str] = []
    done = threading.Event()

    def on_result(text: str, latency: float, is_partial: bool, speaker: str) -> None:
        if is_partial:
            return
        results.append(text)
        print(f"   识别：{text}（耗时 {latency:.1f}s）")

    transcriber = Transcriber(
        model_name=settings.asr_model,
        language=settings.asr_language,
        device=settings.asr_device,
        compute_type=settings.asr_compute_type,
        on_result=on_result,
        on_ready=done.set,
        on_error=lambda message: print(f"   ⚠ 识别异常：{message}"),
    )
    transcriber.start()
    if not done.wait(timeout=120):
        print("   模型加载超时")
        transcriber.stop()
        return 1
    for segment in segments:
        transcriber.submit(segment, "我")
    deadline = time.monotonic() + 60
    while results == [] and time.monotonic() < deadline:
        time.sleep(0.5)
    transcriber.stop()

    if not results:
        print("   ❌ 未识别出任何文本")
        return 1

    print("4) DeepSeek 翻译…")
    client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        model=settings.deepseek_model,
    )
    for text in results:
        print(f"   原文：{text}")
        print(f"   翻译：{client.translate(text)}")

    print("\n✅ 端到端链路验证通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
