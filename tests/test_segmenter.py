import numpy as np

from app.audio.segmenter import Segmenter


SR = 16000


def tone(duration: float = 1.0, amplitude: int = 8000) -> np.ndarray:
    t = np.arange(int(SR * duration)) / SR
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.int16)


def make_segmenter(**kwargs) -> Segmenter:
    defaults = dict(
        sample_rate=SR,
        min_speech=0.1,
        silence_pad=0.2,
        max_duration=5.0,
        energy_threshold=2000,
    )
    defaults.update(kwargs)
    return Segmenter(**defaults)


def test_single_utterance() -> None:
    seg = make_segmenter()
    audio = np.concatenate([np.zeros(SR), tone(duration=1.0), np.zeros(SR)])
    out = seg.feed(audio)
    assert len(out) == 1
    assert out[0].size > SR * 0.5


def test_silence_only_returns_nothing() -> None:
    seg = make_segmenter()
    assert seg.feed(np.zeros(SR * 2, dtype=np.int16)) == []


def test_max_duration_splits_long_speech() -> None:
    seg = make_segmenter(max_duration=0.5, silence_pad=0.2)
    out = seg.feed(tone(duration=2.0))
    assert len(out) >= 3
    for part in out:
        assert part.size <= SR * 0.6 + seg.frame_len


def test_flush_returns_pending_speech() -> None:
    seg = make_segmenter()
    out = seg.feed(tone(duration=1.0))
    assert out == []  # 未到静音边界
    flushed = seg.flush()
    assert len(flushed) == 1


def test_reset_clears_state() -> None:
    seg = make_segmenter()
    seg.feed(tone(duration=1.0))
    seg.reset()
    assert seg.feed(np.zeros(SR, dtype=np.int16)) == []


def test_snapshot_returns_current_speech() -> None:
    seg = make_segmenter()
    assert seg.snapshot().size == 0
    seg.feed(tone(duration=0.6))
    assert seg.in_speech
    snapshot = seg.snapshot()
    assert snapshot.size > 0
    # 快照不应影响分段结果
    out = seg.feed(np.zeros(SR, dtype=np.int16))
    assert len(out) == 1
    assert seg.snapshot().size == 0
