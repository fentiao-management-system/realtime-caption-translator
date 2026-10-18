from __future__ import annotations

import threading
from typing import Optional

from .client import DeepSeekClient


SYSTEM_PROMPT = (
    "你是一个实时对话助手。用户正在使用录音对话软件，你会看到一段正在进行的中文对话记录"
    "（可能包含摘要和历史问答，每条记录前会标注说话人）。请结合对话内容回答问题："
    "如果问题涉及对话中提到的事实、观点或安排，请优先引用对话内容；"
    "如果问题与对话无关，正常回答即可。回答用简体中文（不要使用繁体字），准确、简洁。"
)


def _bigrams(text: str) -> set[str]:
    text = (text or "").strip()
    if len(text) < 2:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


class ConversationMemory:
    """对话记忆：滚动窗口 + 自动摘要 + 关键词检索（长对话增强）。"""

    def __init__(
        self,
        client: DeepSeekClient,
        max_recent_turns: int = 30,
        summarize_every: int = 15,
        recall_k: int = 5,
    ) -> None:
        self._client = client
        self._max_recent_turns = max_recent_turns
        self._summarize_every = summarize_every
        self._recall_k = recall_k
        self._lock = threading.Lock()
        self._summary = ""
        self._recent: list[str] = []
        self._history: list[str] = []
        self._qa: list[dict] = []
        self._pending_summary = False
        self._summarizing_count = 0

    # ---------- 写入 ----------

    def add_transcript(self, text: str, speaker: str = "") -> Optional[list[str]]:
        """记录一句识别文本（带说话人前缀）。

        当需要触发摘要时返回待摘要的文本块（调用方负责异步总结），否则返回 None。
        """
        formatted = f"{speaker}：{text}" if speaker else text
        with self._lock:
            self._history.append(formatted)
            self._recent.append(formatted)
            if len(self._recent) >= self._summarize_every and not self._pending_summary:
                self._pending_summary = True
                self._summarizing_count = len(self._recent)
                return list(self._recent)
            return None

    def add_qa(self, question: str, answer: str) -> None:
        with self._lock:
            self._qa.append({"q": question, "a": answer})

    # ---------- 摘要 ----------

    def summary_snapshot(self) -> str:
        with self._lock:
            return self._summary

    def complete_summary(self, new_summary: str) -> None:
        with self._lock:
            self._summary = new_summary
            del self._recent[: self._summarizing_count]
            self._summarizing_count = 0
            self._pending_summary = False

    def cancel_pending_summary(self) -> None:
        with self._lock:
            self._pending_summary = False

    # ---------- 检索 ----------

    def recall(self, question: str, k: int | None = None) -> list[str]:
        """从全部历史对话中检索与问题最相关的片段（字符二元组重合度）。"""
        limit = k if k is not None else self._recall_k
        question_grams = _bigrams(question)
        if not question_grams:
            return []
        with self._lock:
            history = list(self._history)
            recent = set(history[-self._max_recent_turns :])

        scored: list[tuple[float, str]] = []
        for turn in history:
            grams = _bigrams(turn)
            if not grams:
                continue
            score = len(question_grams & grams) / len(question_grams)
            if score > 0:
                scored.append((score, turn))
        if not scored:
            return []
        scored.sort(key=lambda item: item[0], reverse=True)
        return [turn for _, turn in scored if turn not in recent][:limit]

    # ---------- 上下文构造 ----------

    def build_context(self, question: str | None = None) -> list[dict]:
        """构造发送给 DeepSeek 的上下文消息列表（不含当前问题）。"""
        with self._lock:
            summary = self._summary
            recent = list(self._recent[-self._max_recent_turns :])
            qa = list(self._qa[-10:])

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if summary:
            messages.append(
                {
                    "role": "system",
                    "content": f"以下是之前对话内容的摘要，回答时请参考：\n{summary}",
                }
            )
        if question:
            recalled = self.recall(question)
            if recalled:
                joined = "\n".join(f"- {turn}" for turn in recalled)
                messages.append(
                    {
                        "role": "system",
                        "content": f"以下是从更早对话中检索到的相关片段，回答时可以参考：\n{joined}",
                    }
                )
        for turn in recent:
            messages.append({"role": "user", "content": turn})
        for item in qa:
            messages.append({"role": "user", "content": item["q"]})
            messages.append({"role": "assistant", "content": item["a"]})
        return messages

    def reset(self) -> None:
        with self._lock:
            self._summary = ""
            self._recent.clear()
            self._history.clear()
            self._qa.clear()
            self._pending_summary = False
            self._summarizing_count = 0
