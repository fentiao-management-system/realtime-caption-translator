from __future__ import annotations

import collections
import threading
import time
from typing import Callable, Optional

import numpy as np
import pyaudiowpatch as pyaudio


def _device_sort_key(info: dict) -> str:
    return str(info.get("name", ""))


def discover_devices() -> dict:
    """枚举音频设备，返回麦克风列表、系统声音回环设备列表及默认设备。"""
    p = pyaudio.PyAudio()
    result: dict = {"mic": [], "loopback": [], "default_mic": None, "default_loopback": None}
    try:
        loopbacks = list(p.get_loopback_device_info_generator())
        for info in loopbacks:
            result["loopback"].append(info)
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info.get("isLoopbackDevice"):
                continue
            if int(info.get("maxInputChannels", 0)) > 0:
                result["mic"].append(info)

        result["mic"].sort(key=_device_sort_key)
        result["loopback"].sort(key=_device_sort_key)

        try:
            default_mic = p.get_default_input_device_info()
            result["default_mic"] = int(default_mic["index"])
        except OSError:
            result["default_mic"] = result["mic"][0]["index"] if result["mic"] else None

        # 默认系统声音回环：默认输出设备对应的回环设备
        try:
            wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_out = p.get_device_info_by_index(int(wasapi["defaultOutputDevice"]))
            for loopback in result["loopback"]:
                if default_out["name"] in str(loopback["name"]):
                    result["default_loopback"] = int(loopback["index"])
                    break
            if result["default_loopback"] is None and result["loopback"]:
                result["default_loopback"] = int(result["loopback"][0]["index"])
        except (OSError, KeyError):
            if result["loopback"]:
                result["default_loopback"] = int(result["loopback"][0]["index"])
    finally:
        p.terminate()
    return result


def resample(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """线性插值重采样，简单够用。"""
    if src_rate == dst_rate or audio.size == 0:
        return audio
    n = max(1, int(round(audio.size * dst_rate / src_rate)))
    x = np.arange(n, dtype=np.float64) * (audio.size / n)
    return np.interp(x, np.arange(audio.size, dtype=np.float64), audio.astype(np.float64)).astype(np.int16)


class AudioCapture:
    """同时采集麦克风与系统声音（WASAPI 回环），混合后输出 16k 单声道音频。"""

    def __init__(
        self,
        mic_info: Optional[dict] = None,
        sys_info: Optional[dict] = None,
        mic_volume: float = 1.0,
        sys_volume: float = 1.0,
        sample_rate: int = 16000,
        on_frame: Optional[Callable[[np.ndarray, np.ndarray], None]] = None,
    ) -> None:
        if mic_info is None and sys_info is None:
            raise ValueError("至少需要一个音频输入设备")
        self.pa = pyaudio.PyAudio()
        self.sample_rate = sample_rate
        self.on_frame = on_frame
        self._mic_volume = mic_volume
        self._sys_volume = sys_volume
        self._stopping = False
        self._thread: Optional[threading.Thread] = None
        self._mic = self._open_device(mic_info) if mic_info is not None else None
        self._sys = self._open_device(sys_info) if sys_info is not None else None

    def _open_device(self, info: dict) -> dict:
        channels = max(1, min(2, int(info.get("maxInputChannels", 1))))
        rate = max(8000, int(info.get("defaultSampleRate", 48000)))
        dev = {
            "info": info,
            "channels": channels,
            "rate": rate,
            "queue": collections.deque(),
            "stream": None,
        }
        frames_per_buffer = max(128, int(rate * 0.01))
        stream = self.pa.open(
            format=pyaudio.paInt16,
            channels=channels,
            rate=rate,
            input=True,
            input_device_index=int(info["index"]),
            frames_per_buffer=frames_per_buffer,
            stream_callback=self._make_callback(dev),
        )
        dev["stream"] = stream
        return dev

    def _make_callback(self, dev: dict):
        def callback(in_data, frame_count, time_info, status) -> tuple:
            if in_data is not None and not self._stopping:
                dev["queue"].append(in_data)
            return (None, pyaudio.paContinue)

        return callback

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        target_len = max(1, self.sample_rate // 100)  # 10ms 一帧
        start_time = time.perf_counter()
        i = 0
        while not self._stopping:
            mic = self._device_frame(self._mic, self._mic_volume, target_len)
            sys_audio = self._device_frame(self._sys, self._sys_volume, target_len)
            if self.on_frame is not None:
                self.on_frame(mic, sys_audio)
            i += 1
            deadline = i * 0.01
            time.sleep(max(0.0, deadline - (time.perf_counter() - start_time)))

    def _device_frame(self, dev: Optional[dict], volume: float, target_len: int) -> np.ndarray:
        if dev is None or not dev["queue"]:
            return np.zeros(target_len, dtype=np.int16)
        raw = dev["queue"].popleft()
        audio = np.frombuffer(raw, dtype=np.int16)
        if dev["channels"] > 1 and audio.size >= dev["channels"]:
            audio = audio[: audio.size // dev["channels"] * dev["channels"]].reshape(-1, dev["channels"])
            audio = audio.mean(axis=1).astype(np.int16)
        audio = resample(audio, dev["rate"], self.sample_rate)
        if audio.size < target_len:
            audio = np.pad(audio, (0, target_len - audio.size))
        else:
            audio = audio[:target_len]
        if volume != 1.0:
            audio = np.clip(audio * volume, -32768, 32767).astype(np.int16)
        return audio

    def stop(self) -> None:
        self._stopping = True
        if self._thread is not None:
            self._thread.join(timeout=3)
            self._thread = None
        for dev in (self._mic, self._sys):
            if dev is not None and dev["stream"] is not None:
                try:
                    dev["stream"].stop_stream()
                    dev["stream"].close()
                except Exception:
                    pass
                dev["stream"] = None
        try:
            self.pa.terminate()
        except Exception:
            pass
