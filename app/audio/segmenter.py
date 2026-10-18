from __future__ import annotations

import numpy as np


class Segmenter:
    """把连续的 16k 单声道 int16 音频流切分为独立的语音段。

    基于能量检测的 VAD 状态机：检测到持续语音后开始积累，
    遇到足够长的静音或达到最长时长时输出一个语音段。
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        min_speech: float = 0.35,
        silence_pad: float = 0.8,
        max_duration: float = 10.0,
        frame_ms: int = 20,
        energy_threshold: float = 300.0,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_len = int(sample_rate * frame_ms / 1000)
        self.min_speech_frames = max(1, int(min_speech * 1000 / frame_ms))
        self.silence_pad_frames = max(1, int(silence_pad * 1000 / frame_ms))
        self.max_frames = int(max_duration * 1000 / frame_ms)
        self.energy_threshold = float(energy_threshold)

        self._pending = np.zeros(0, dtype=np.int16)
        self._candidate = np.zeros(0, dtype=np.int16)
        self._segment = np.zeros(0, dtype=np.int16)
        self._silence_frames = 0
        self._in_speech = False

    def reset(self) -> None:
        self._pending = np.zeros(0, dtype=np.int16)
        self._candidate = np.zeros(0, dtype=np.int16)
        self._segment = np.zeros(0, dtype=np.int16)
        self._silence_frames = 0
        self._in_speech = False

    @property
    def in_speech(self) -> bool:
        return self._in_speech

    def snapshot(self) -> np.ndarray:
        """返回当前未完成的语音段副本，用于生成低延迟临时字幕。"""
        if not self._in_speech or self._segment.size == 0:
            return np.zeros(0, dtype=np.int16)
        return self._segment.copy()

    @staticmethod
    def _frame_energy(frame: np.ndarray) -> float:
        if frame.size == 0:
            return 0.0
        return float(np.sqrt(np.mean(np.square(frame.astype(np.float32)))))

    def feed(self, audio: np.ndarray) -> list[np.ndarray]:
        """输入一段音频，返回切分完成的语音段列表。"""
        if audio.size == 0:
            return []
        self._pending = np.concatenate([self._pending, audio])
        segments: list[np.ndarray] = []

        while self._pending.size >= self.frame_len:
            frame = self._pending[: self.frame_len]
            self._pending = self._pending[self.frame_len :]
            is_speech = self._frame_energy(frame) >= self.energy_threshold

            if not self._in_speech:
                if is_speech:
                    self._candidate = np.concatenate([self._candidate, frame])
                    if self._candidate.size >= self.min_speech_frames * self.frame_len:
                        self._in_speech = True
                        self._segment = self._candidate
                        self._candidate = np.zeros(0, dtype=np.int16)
                        self._silence_frames = 0
                else:
                    self._candidate = np.zeros(0, dtype=np.int16)
                continue

            self._segment = np.concatenate([self._segment, frame])
            if is_speech:
                self._silence_frames = 0
            else:
                self._silence_frames += 1

            if self._silence_frames >= self.silence_pad_frames or self._segment.size >= self.max_frames * self.frame_len:
                segments.append(self._trim(self._segment))
                self._segment = np.zeros(0, dtype=np.int16)
                self._in_speech = False
                self._candidate = np.zeros(0, dtype=np.int16)
                self._silence_frames = 0

        return segments

    def flush(self) -> list[np.ndarray]:
        """停止时调用，输出未完成的语音段。"""
        segments: list[np.ndarray] = []
        if self._in_speech and self._segment.size >= self.min_speech_frames * self.frame_len:
            segments.append(self._trim(self._segment))
        self.reset()
        return segments

    def _trim(self, segment: np.ndarray) -> np.ndarray:
        """去掉首尾的静音帧。"""
        if segment.size < self.frame_len:
            return segment
        n = segment.size // self.frame_len
        frames = segment[: n * self.frame_len].reshape(n, self.frame_len)
        energies = np.sqrt(np.mean(frames.astype(np.float32) ** 2, axis=1))
        speech = energies >= self.energy_threshold
        if not speech.any():
            return segment
        first = int(np.argmax(speech))
        last = int(n - 1 - np.argmax(speech[::-1]))
        return frames[first : last + 1].reshape(-1).copy()
