from __future__ import annotations

import time
from typing import Optional

import requests


class DeepSeekError(RuntimeError):
    pass


class DeepSeekClient:
    """DeepSeek 聊天补全客户端（OpenAI 兼容接口）。"""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        api_key = (api_key or "").strip()
        if not api_key:
            raise DeepSeekError("未配置 DEEPSEEK_API_KEY，请在 .env 文件中填写")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(1.0 + attempt)
                    continue
                raise DeepSeekError(f"网络请求失败：{exc}") from exc

            if response.status_code == 200:
                data = response.json()
                try:
                    return data["choices"][0]["message"]["content"].strip()
                except (KeyError, IndexError, TypeError) as exc:
                    raise DeepSeekError(f"DeepSeek 返回格式异常：{data}") from exc

            last_error = DeepSeekError(f"DeepSeek API 错误 {response.status_code}: {response.text[:300]}")
            if attempt < self.max_retries:
                time.sleep(1.0 + attempt)
                continue
            raise last_error
        raise last_error or DeepSeekError("请求失败")

    def translate(
        self,
        text: str,
        context: Optional[list[tuple[str, str]]] = None,
        glossary: Optional[dict[str, str]] = None,
    ) -> str:
        parts = [
            "你是一名专业翻译。把用户提供的中文口语内容翻译成自然、地道的英文。"
            "只输出译文本身，不要加解释、不要加引号。"
        ]
        if glossary:
            pairs = "；".join(f"{zh} → {en}" for zh, en in glossary.items())
            parts.append(f"术语对照（必须严格遵循）：{pairs}")
        if context:
            lines = "\n".join(f"原文：{zh}\n译文：{en}" for zh, en in context)
            parts.append(f"以下是前文的原文与译文，请保持术语、语气与指代一致：\n{lines}")
        messages = [
            {"role": "system", "content": "\n\n".join(parts)},
            {"role": "user", "content": text},
        ]
        return self.chat(messages, temperature=0.3, max_tokens=1024)

    def summarize(self, content: str) -> str:
        messages = [
            {
                "role": "system",
                "content": (
                    "你是对话记录员。用简洁的简体中文总结下面这段对话的要点（不要使用繁体字），"
                    "保留人名、数字、结论和待办事项等关键信息，不超过 250 字。"
                    "只输出总结本身。"
                ),
            },
            {"role": "user", "content": content},
        ]
        return self.chat(messages, temperature=0.3, max_tokens=600)
