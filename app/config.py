from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # 依赖尚未安装时允许导入模块
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Settings:
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    asr_model: str = "small"
    asr_device: str = "auto"
    asr_compute_type: str = "int8"
    asr_language: str = "zh"
    target_language: str = "en"

    sample_rate: int = 16000
    energy_threshold: int = 300
    mic_volume: float = 1.0
    sys_volume: float = 1.0

    max_recent_turns: int = 30
    summarize_every: int = 15
    stream_hop_ms: int = 700

    session_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "sessions")
    glossary_path: Path = field(default_factory=lambda: PROJECT_ROOT / "glossary.json")


def load_env() -> None:
    if load_dotenv is not None:
        load_dotenv(PROJECT_ROOT / ".env")


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value is not None and value.strip() else default
    except ValueError:
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value is not None and value.strip() else default
    except ValueError:
        return default


def load_settings() -> Settings:
    load_env()
    s = Settings()
    s.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    s.deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", s.deepseek_base_url).strip().rstrip("/")
    s.deepseek_model = os.getenv("DEEPSEEK_MODEL", s.deepseek_model).strip() or s.deepseek_model
    s.asr_model = os.getenv("ASR_MODEL", s.asr_model).strip() or s.asr_model
    s.asr_device = os.getenv("ASR_DEVICE", s.asr_device).strip() or s.asr_device
    s.asr_compute_type = os.getenv("ASR_COMPUTE_TYPE", s.asr_compute_type).strip() or s.asr_compute_type
    s.asr_language = os.getenv("ASR_LANGUAGE", s.asr_language).strip() or s.asr_language
    s.target_language = os.getenv("TARGET_LANGUAGE", s.target_language).strip() or s.target_language
    s.sample_rate = _as_int(os.getenv("SAMPLE_RATE"), s.sample_rate)
    s.energy_threshold = _as_int(os.getenv("ENERGY_THRESHOLD"), s.energy_threshold)
    s.mic_volume = _as_float(os.getenv("MIC_VOLUME"), s.mic_volume)
    s.sys_volume = _as_float(os.getenv("SYS_VOLUME"), s.sys_volume)
    s.max_recent_turns = _as_int(os.getenv("MAX_RECENT_TURNS"), s.max_recent_turns)
    s.summarize_every = _as_int(os.getenv("SUMMARIZE_EVERY"), s.summarize_every)
    s.stream_hop_ms = _as_int(os.getenv("STREAM_HOP_MS"), s.stream_hop_ms)
    glossary = os.getenv("GLOSSARY_PATH", "").strip()
    if glossary:
        s.glossary_path = Path(glossary)
    return s
