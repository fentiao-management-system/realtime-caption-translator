import numpy as np

from app.config import Settings
from app.controller import SPEAKER_MIC, SPEAKER_SYS, AppController


SR = 16000


class FakeTranscriber:
    def __init__(self) -> None:
        self.finals: list[tuple] = []
        self.partials: list[tuple] = []

    def submit(self, audio, speaker: str = "") -> None:
        self.finals.append((audio, speaker))

    def submit_partial(self, audio, speaker: str = "") -> None:
        self.partials.append((audio, speaker))


def tone(duration: float, amplitude: int = 8000) -> np.ndarray:
    t = np.arange(int(SR * duration)) / SR
    return (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.int16)


def make_controller() -> AppController:
    settings = Settings()
    settings.stream_hop_ms = 100
    return AppController(settings)


def test_partial_scheduled_while_speaking_for_mic() -> None:
    controller = make_controller()
    fake = FakeTranscriber()
    controller._transcriber = fake

    controller._on_frame(tone(0.5), np.zeros(0, dtype=np.int16))
    assert fake.partials, "说话过程中应产生临时字幕任务"
    assert fake.partials[0][1] == SPEAKER_MIC

    controller._on_frame(np.zeros(SR, dtype=np.int16), np.zeros(0, dtype=np.int16))
    assert fake.finals, "静音后应提交最终识别任务"
    assert fake.finals[0][1] == SPEAKER_MIC


def test_system_audio_tagged_as_other_speaker() -> None:
    controller = make_controller()
    fake = FakeTranscriber()
    controller._transcriber = fake

    controller._on_frame(np.zeros(0, dtype=np.int16), tone(0.5))
    controller._on_frame(np.zeros(0, dtype=np.int16), np.zeros(SR, dtype=np.int16))
    assert fake.finals, "系统声音应产生最终识别任务"
    assert fake.finals[0][1] == SPEAKER_SYS


def test_no_partial_without_speech() -> None:
    controller = make_controller()
    fake = FakeTranscriber()
    controller._transcriber = fake

    controller._on_frame(np.zeros(SR, dtype=np.int16), np.zeros(SR, dtype=np.int16))
    assert not fake.partials
    assert not fake.finals
