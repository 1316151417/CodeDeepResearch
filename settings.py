"""
Settings loader - loads configuration from settings.json with defaults.
"""
import json
import os

_DEFAULTS = {
    "provider": "anthropic",
    "lite_model": "deepseek-chat",
    "pro_model": "deepseek-chat",
    "max_model": "deepseek-reasoner",
    "max_tokens": 16384,
    "max_sub_agent_steps": 30,
    "research_parallel": False,
    "research_threads": 4,
}

_settings = None


def load_settings(path: str | None = None) -> dict:
    """Load settings from JSON file, falling back to defaults."""
    global _settings
    if _settings is not None:
        return _settings

    if path is None:
        candidates = [
            os.path.join(os.getcwd(), "settings.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json"),
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                path = candidate
                break

    if path and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_settings = json.load(f)
        _settings = {**_DEFAULTS, **user_settings}
    else:
        _settings = dict(_DEFAULTS)

    return _settings


def get_settings() -> dict:
    return load_settings()


def get_provider() -> str:
    return load_settings()["provider"]


def get_model() -> str:
    """Legacy function - returns lite model for backward compatibility."""
    return get_lite_model()


def get_lite_model() -> str:
    return load_settings().get("lite_model", _DEFAULTS["lite_model"])


def get_pro_model() -> str:
    return load_settings().get("pro_model", _DEFAULTS["pro_model"])


def get_max_model() -> str:
    return load_settings().get("max_model", _DEFAULTS["max_model"])


def get_max_tokens() -> int:
    return load_settings()["max_tokens"]


def reset_settings() -> None:
    """Reset settings cache (useful for testing)."""
    global _settings
    _settings = None
