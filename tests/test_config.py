from app.config import load_settings


def test_env_overrides(monkeypatch) -> None:
    monkeypatch.setenv("ASR_MODEL", "base")
    monkeypatch.setenv("SAMPLE_RATE", "32000")
    monkeypatch.setenv("ENERGY_THRESHOLD", "999")
    monkeypatch.setenv("MIC_VOLUME", "0.5")
    settings = load_settings()
    assert settings.asr_model == "base"
    assert settings.sample_rate == 32000
    assert settings.energy_threshold == 999
    assert settings.mic_volume == 0.5


def test_defaults_loaded_from_env_file() -> None:
    settings = load_settings()
    assert settings.deepseek_api_key  # .env 中已配置
    assert settings.deepseek_base_url == "https://api.deepseek.com"
    assert settings.asr_language == "zh"
    assert settings.target_language == "en"
