from __future__ import annotations

import os
import queue
import site
import threading
import time
from typing import Callable, Optional

import numpy as np

_IDLE = object()
_STOP = object()


def _ensure_nvidia_runtime_on_path() -> None:
    """把 pip 安装的 nvidia-* 包里的 bin 目录加入 PATH，供 ctranslate2 加载 cuBLAS。"""
    existing = os.environ.get("PATH", "")
    found = False
    for base in site.getsitepackages():
        nvidia_dir = os.path.join(base, "nvidia")
        if not os.path.isdir(nvidia_dir):
            continue
        for pkg_dir in os.listdir(nvidia_dir):
            bin_dir = os.path.join(nvidia_dir, pkg_dir, "bin")
            if os.path.isdir(bin_dir) and bin_dir not in existing:
                existing = bin_dir + os.pathsep + existing
                found = True
    if found:
        os.environ["PATH"] = existing


class Transcriber:
    """faster-whisper 流式转写。

    支持两种任务：
    - 最终结果（final）：一整段语音，识别后作为正式字幕；
    - 临时结果（partial）：说话过程中的快照，用于低延迟预览，只保留最新一个任务。
    """

    def __init__(
        self,
        model_name: str = "small",
        language: str = "zh",
        device: str = "auto",
        compute_type: str = "int8",
        on_result: Optional[Callable[[str, float, bool, str], None]] = None,
        on_ready: Optional[Callable[[], None]] = None,
        on_warning: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.on_result = on_result
        self.on_ready = on_ready
        self.on_warning = on_warning
        self.on_error = on_error
        self._final_queue: "queue.Queue" = queue.Queue()
        self._partial_lock = threading.Lock()
        self._partial_job: Optional[tuple] = None
        self._thread: Optional[threading.Thread] = None
        self._model = None
        self._simplifier = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def submit(self, audio: np.ndarray, speaker: str = "") -> None:
        if audio is None or audio.size == 0:
            return
        self._final_queue.put((audio, speaker, False))

    def submit_partial(self, audio: np.ndarray, speaker: str = "") -> None:
        if audio is None or audio.size < 4800:  # 至少 0.3 秒
            return
        with self._partial_lock:
            self._partial_job = (audio, speaker, True)

    def _run(self) -> None:
        try:
            _ensure_nvidia_runtime_on_path()
            from faster_whisper import WhisperModel

            self._model, used_device = self._load_model()
            if used_device != self.device and used_device == "cpu":
                if self.on_warning is not None:
                    self.on_warning(
                        f"GPU 加速不可用（缺少 CUDA 运行库），已回退 CPU 运行 {self.model_name} 模型"
                    )
        except Exception as exc:
            if self.on_error is not None:
                hint = ""
                if "ConnectTimeout" in str(exc) or "Connection error" in str(exc):
                    hint = "（模型下载超时，可在 .env 中设置 HF_ENDPOINT=https://hf-mirror.com 后重试）"
                self.on_error(f"语音识别模型加载失败：{exc}{hint}")
            return

        if self.on_ready is not None:
            self.on_ready()

        try:
            from opencc import OpenCC

            self._simplifier = OpenCC("t2s")
        except Exception:
            self._simplifier = None
            if self.on_warning is not None:
                self.on_warning(
                    "未安装 opencc，识别结果可能包含繁体字（pip install opencc-python-reimplemented）"
                )

        while True:
            job = self._next_job()
            if job is _STOP:
                break
            if job is _IDLE:
                continue
            audio, speaker, is_partial = job
            try:
                started = time.perf_counter()
                segments, _ = self._model.transcribe(
                    audio.astype(np.float32) / 32768.0,
                    language=self.language,
                    beam_size=1,
                    vad_filter=not is_partial,
                    condition_on_previous_text=False,
                    initial_prompt="以下是普通话的句子。",
                )
                text = "".join(seg.text for seg in segments).strip()
                if text and self._simplifier is not None:
                    text = self._simplifier.convert(text)
                elapsed = time.perf_counter() - started
                if text and self.on_result is not None:
                    self.on_result(text, elapsed, is_partial, speaker)
            except Exception as exc:
                if self.on_error is not None:
                    self.on_error(f"语音识别失败：{exc}")

    def _next_job(self):
        with self._partial_lock:
            if self._partial_job is not None:
                job = self._partial_job
                self._partial_job = None
                return job
        try:
            return self._final_queue.get(timeout=0.05)
        except queue.Empty:
            return _IDLE

    def _load_model(self):
        """依次尝试配置的设备与 CPU，返回 (模型, 实际设备)。"""
        from faster_whisper import WhisperModel

        devices = [self.device]
        if self.device != "cpu":
            devices.append("cpu")
        last_exception: Optional[Exception] = None
        for device in devices:
            compute_types = [self.compute_type]
            if device.startswith("cuda") and self.compute_type in ("int8", "int8_float32"):
                compute_types = ["int8_float16", "float16"]
            for compute_type in dict.fromkeys(compute_types):
                try:
                    model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
                    return model, device
                except Exception as exc:
                    last_exception = exc
        raise last_exception or RuntimeError("模型加载失败")

    def stop(self) -> None:
        self._final_queue.put(_STOP)
        if self._thread is not None:
            self._thread.join(timeout=10)
            self._thread = None
