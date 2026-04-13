"""
Settings loader - loads configuration from settings.json with defaults.
"""
import json
import os

_DEFAULTS = {
    "lite": {
        "provider": "anthropic",
        "base_url": "https://api.deepseek.com/anthropic",
        "api_key": "${DEEPSEEK_API_KEY}",
        "model": "deepseek-chat",
        "max_tokens": 16384,
    },
    "pro": {
        "provider": "anthropic",
        "base_url": "https://api.deepseek.com/anthropic",
        "api_key": "${DEEPSEEK_API_KEY}",
        "model": "deepseek-chat",
        "max_tokens": 16384,
    },
    "max": {
        "provider": "openai",
        "base_url": "https://api.deepseek.com",
        "api_key": "${DEEPSEEK_API_KEY}",
        "model": "deepseek-reasoner",
        "max_tokens": 16384,
    },
    "max_sub_agent_steps": 30,
    "research_parallel": False,
    "research_threads": 4,
    "debug": False,
}

_settings = None


def _expand_env_vars(obj):
    """Recursively expand ${VAR} environment variables in strings."""
    if isinstance(obj, str):
        return os.path.expandvars(obj)
    elif isinstance(obj, dict):
        return {k: _expand_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_expand_env_vars(item) for item in obj]
    return obj


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
        merged = {**_DEFAULTS, **user_settings}
        # Expand env vars in tier configs
        for tier in ["lite", "pro", "max"]:
            if tier in merged and tier in _DEFAULTS:
                merged[tier] = {**_DEFAULTS[tier], **merged.get(tier, {})}
        _settings = _expand_env_vars(merged)
    else:
        _settings = _expand_env_vars(dict(_DEFAULTS))

    return _settings


def get_settings() -> dict:
    return load_settings()


def get_provider() -> str:
    """Legacy function - returns lite provider for backward compatibility."""
    return get_lite_config()["provider"]


def get_model() -> str:
    """Legacy function - returns lite model for backward compatibility."""
    return get_lite_model()


def get_lite_config() -> dict:
    return load_settings()["lite"]


def get_pro_config() -> dict:
    return load_settings()["pro"]


def get_max_config() -> dict:
    return load_settings()["max"]


def get_lite_model() -> str:
    return get_lite_config()["model"]


def get_pro_model() -> str:
    return get_pro_config()["model"]


def get_max_model() -> str:
    return get_max_config()["model"]


def get_max_tokens() -> int:
    return load_settings()["max_tokens"]


def reset_settings() -> None:
    """Reset settings cache (useful for testing)."""
    global _settings
    _settings = None
