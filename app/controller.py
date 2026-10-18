from __future__ import annotations

import datetime
import json
import queue
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from .ai.client import DeepSeekClient
from .ai.memory import ConversationMemory
from .asr.transcriber import Transcriber
from .audio.capture import AudioCapture
from .audio.segmenter import Segmenter
from .config import Settings
from .storage.recorder import SessionRecorder

SPEAKER_MIC = "我"
SPEAKER_SYS = "对方"


class AppController(QObject):
    """串联音频采集 → 双路分段 → 流式识别 → 翻译/摘要/问答 的控制器。"""

    status_changed = Signal(str)
    subtitle_added = Signal(int, str, str, str)  # id, 原文, 时间, 说话人
    partial_text = Signal(str, str)  # 临时文本, 说话人
    translation_ready = Signal(int, str)  # id, 译文
    answer_ready = Signal(str, str)  # 问题, 回答
    error_occurred = Signal(str)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.client: Optional[DeepSeekClient] = None
        self.memory: Optional[ConversationMemory] = None
        self.recorder = SessionRecorder(settings.session_dir)
        self._capture: Optional[AudioCapture] = None
        self._transcriber: Optional[Transcriber] = None
        self._mic_segmenter = Segmenter(
            sample_rate=settings.sample_rate,
            energy_threshold=settings.energy_threshold,
        )
        self._sys_segmenter = Segmenter(
            sample_rate=settings.sample_rate,
            energy_threshold=settings.energy_threshold,
        )
        self._translate_queue: "queue.Queue[Optional[tuple]]" = queue.Queue()
        self._summarize_queue: "queue.Queue[Optional[list]]" = queue.Queue()
        self._translate_thread: Optional[threading.Thread] = None
        self._summarize_thread: Optional[threading.Thread] = None
        self._running = False
        self._subtitle_id = 0
        self._recent_pairs: deque[tuple[str, str]] = deque(maxlen=3)
        self._glossary: dict[str, str] = {}
        self._last_partial: dict[str, float] = {SPEAKER_MIC: 0.0, SPEAKER_SYS: 0.0}

    # ---------- 公共接口 ----------

    def start_recording(
        self,
        mic_info: Optional[dict] = None,
        sys_info: Optional[dict] = None,
        mic_volume: float = 1.0,
        sys_volume: float = 1.0,
    ) -> None:
        if self._running:
            return
        try:
            self._ensure_ai()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return

        try:
            self.recorder.start()
            self._mic_segmenter.reset()
            self._sys_segmenter.reset()
            self._recent_pairs.clear()
            self._glossary = self._load_glossary()
            self._translate_queue = queue.Queue()
            self._summarize_queue = queue.Queue()
            self._last_partial = {SPEAKER_MIC: 0.0, SPEAKER_SYS: 0.0}

            self._capture = AudioCapture(
                mic_info=mic_info,
                sys_info=sys_info,
                mic_volume=mic_volume,
                sys_volume=sys_volume,
                sample_rate=self.settings.sample_rate,
                on_frame=self._on_frame,
            )
            self._capture.start()

            self._transcriber = Transcriber(
                model_name=self.settings.asr_model,
                language=self.settings.asr_language,
                device=self.settings.asr_device,
                compute_type=self.settings.asr_compute_type,
                on_result=self._on_asr_result,
                on_ready=lambda: self.status_changed.emit("语音识别模型已就绪"),
                on_warning=self.status_changed.emit,
                on_error=self.error_occurred.emit,
            )
            self._transcriber.start()

            self._translate_thread = threading.Thread(target=self._translate_worker, daemon=True)
            self._summarize_thread = threading.Thread(target=self._summarize_worker, daemon=True)
            self._translate_thread.start()
            self._summarize_thread.start()
        except Exception as exc:
            self.error_occurred.emit(f"启动录音失败：{exc}")
            if self._capture is not None:
                self._capture.stop()
                self._capture = None
            if self._transcriber is not None:
                self._transcriber.stop()
                self._transcriber = None
            self.recorder.close()
            return

        self._running = True
        self.status_changed.emit("开始录音…（首次运行会自动下载识别模型，请稍候）")

    def stop_recording(self) -> None:
        if not self._running:
            return
        self._running = False

        if self._capture is not None:
            self._capture.stop()
            self._capture = None
        if self._transcriber is not None:
            for segment in self._mic_segmenter.flush():
                self._transcriber.submit(segment, SPEAKER_MIC)
            for segment in self._sys_segmenter.flush():
                self._transcriber.submit(segment, SPEAKER_SYS)
            self._transcriber.stop()
            self._transcriber = None

        self._translate_queue.put(None)
        self._summarize_queue.put(None)
        for worker in (self._translate_thread, self._summarize_thread):
            if worker is not None:
                worker.join(timeout=5)
        self._translate_thread = None
        self._summarize_thread = None
        self.recorder.close()

        path = self.recorder.path
        self.status_changed.emit(f"已停止，记录保存至：{path}")

    def ask(self, question: str) -> None:
        question = question.strip()
        if not question:
            return
        try:
            self._ensure_ai()
        except Exception as exc:
            self.error_occurred.emit(str(exc))
            return
        threading.Thread(target=self._ask_worker, args=(question,), daemon=True).start()

    def clear_memory(self) -> None:
        if self.memory is not None:
            self.memory.reset()
        self.status_changed.emit("对话上下文已清空")

    def shutdown(self) -> None:
        self.stop_recording()

    # ---------- 内部实现 ----------

    def _ensure_ai(self) -> None:
        if self.client is None:
            self.client = DeepSeekClient(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                model=self.settings.deepseek_model,
            )
        if self.memory is None:
            self.memory = ConversationMemory(
                client=self.client,
                max_recent_turns=self.settings.max_recent_turns,
                summarize_every=self.settings.summarize_every,
            )

    def _load_glossary(self) -> dict[str, str]:
        path = Path(self.settings.glossary_path)
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): str(value) for key, value in data.items()}

    def _on_frame(self, mic, sys_frame) -> None:
        self._feed_source(SPEAKER_MIC, self._mic_segmenter, mic)
        self._feed_source(SPEAKER_SYS, self._sys_segmenter, sys_frame)

    def _feed_source(self, speaker: str, segmenter: Segmenter, frame) -> None:
        if frame is None or frame.size == 0:
            return
        for segment in segmenter.feed(frame):
            if self._transcriber is not None:
                self._transcriber.submit(segment, speaker)

        now = time.monotonic()
        hop_sec = max(0.2, self.settings.stream_hop_ms / 1000.0)
        if segmenter.in_speech and now - self._last_partial[speaker] >= hop_sec:
            snapshot = segmenter.snapshot()
            if snapshot.size > 0 and self._transcriber is not None:
                self._last_partial[speaker] = now
                self._transcriber.submit_partial(snapshot, speaker)

    def _on_asr_result(self, text: str, latency: float, is_partial: bool, speaker: str) -> None:
        if is_partial:
            self.partial_text.emit(text, speaker)
            return

        sid = self._subtitle_id
        self._subtitle_id += 1
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.subtitle_added.emit(sid, text, ts, speaker)
        self.status_changed.emit(f"识别成功（{speaker}，耗时 {latency:.1f}s）")

        if self.memory is not None:
            chunk = self.memory.add_transcript(text, speaker)
            if chunk is not None:
                self._summarize_queue.put(chunk)
        self.recorder.write(type="transcript", speaker=speaker, text=text)
        self._translate_queue.put((sid, text))

    def _translate_worker(self) -> None:
        while True:
            item = self._translate_queue.get()
            if item is None:
                break
            sid, text = item
            try:
                translation = self.client.translate(
                    text,
                    context=list(self._recent_pairs),
                    glossary=self._glossary or None,
                )
            except Exception as exc:
                self.error_occurred.emit(f"翻译失败：{exc}")
                continue
            self._recent_pairs.append((text, translation))
            self.translation_ready.emit(sid, translation)
            self.recorder.write(type="translation", source=text, translation=translation)

    def _summarize_worker(self) -> None:
        while True:
            chunk = self._summarize_queue.get()
            if chunk is None:
                break
            try:
                old_summary = self.memory.summary_snapshot()
                content = f"已有摘要：\n{old_summary or '（无）'}\n\n新增对话：\n" + "\n".join(
                    f"- {turn}" for turn in chunk
                )
                new_summary = self.client.summarize(content)
                self.memory.complete_summary(new_summary)
                self.status_changed.emit("对话摘要已更新")
            except Exception as exc:
                self.memory.cancel_pending_summary()
                self.error_occurred.emit(f"摘要更新失败：{exc}")

    def _ask_worker(self, question: str) -> None:
        try:
            messages = self.memory.build_context(question)
            answer = self.client.chat(
                messages + [{"role": "user", "content": question}],
                temperature=0.7,
                max_tokens=1500,
            )
        except Exception as exc:
            self.error_occurred.emit(f"问答失败：{exc}")
            return
        self.memory.add_qa(question, answer)
        self.recorder.write(type="qa", question=question, answer=answer)
        self.answer_ready.emit(question, answer)
