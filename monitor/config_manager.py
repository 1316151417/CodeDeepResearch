"""
ConfigManager - loads and manages pipeline configuration from YAML.
Supports hot-reload without restarting the pipeline.
"""
import os
import threading
from pathlib import Path
from typing import Any

import yaml

from settings import load_settings, get_settings


class ConfigManager:
    """
    Manages pipeline configuration from config/pipeline.yaml.

    Hot-reload: check_reload() compares file mtime and reloads if changed.
    Falls back to settings.json for missing keys.
    """

    def __init__(self, config_path: str | None = None):
        if config_path is None:
            candidates = [
                Path.cwd() / "config" / "pipeline.yaml",
                Path(__file__).parent.parent / "config" / "pipeline.yaml",
            ]
            for c in candidates:
                if c.exists():
                    config_path = str(c)
                    break
        self._config_path = Path(config_path) if config_path else None
        self._config: dict = {}
        self._mtime: float = 0
        self._lock = threading.RLock()
        self._load()

    def _load(self) -> None:
        """Load config from YAML, falling back to settings.json."""
        with self._lock:
            if self._config_path and self._config_path.exists():
                mtime = os.path.getmtime(self._config_path)
                if mtime != self._mtime:
                    self._mtime = mtime
                    with open(self._config_path, encoding="utf-8") as f:
                        self._config = yaml.safe_load(f) or {}
            else:
                self._config = {}
            # Fill in missing keys from settings.json
            self._fill_from_settings()

    def _fill_from_settings(self) -> None:
        """Fill missing config keys from legacy settings.json."""
        s = get_settings()
        self._config.setdefault("models", {
            "provider": s.get("provider", "anthropic"),
            "lite_model": s.get("lite_model", "deepseek-chat"),
            "pro_model": s.get("pro_model", "deepseek-chat"),
            "max_model": s.get("max_model", "deepseek-reasoner"),
        })
        self._config.setdefault("pipeline", {
            "max_sub_agents": s.get("max_sub_agents", 5),
            "max_sub_agent_steps": s.get("max_sub_agent_steps", 15),
            "max_eval_rounds": s.get("max_eval_rounds", 3),
            "parallel_research": s.get("parallel_research", True),
        })
        self._config.setdefault("server", {
            "url": s.get("server_url", "http://localhost:7890"),
            "auto_start": s.get("monitor_auto_start", True),
        })

    def check_reload(self) -> bool:
        """Check if file changed; reload if so. Returns True if reloaded."""
        if self._config_path and self._config_path.exists():
            mtime = os.path.getmtime(self._config_path)
            if mtime != self._mtime:
                self._load()
                return True
        return False

    def reload(self) -> None:
        """Force reload from disk."""
        self._load()

    def get(self, *keys, default=None) -> Any:
        """Get a nested config value, e.g. get("models", "lite_model")."""
        with self._lock:
            val = self._config
            for k in keys:
                if isinstance(val, dict):
                    val = val.get(k)
                else:
                    return default
                if val is None:
                    return default
            return val

    def get_prompt(self, name: str, **kwargs) -> str:
        """
        Get a prompt template with format kwargs applied.
        e.g. get_prompt("file_filter_system", project_name="foo")
        """
        with self._lock:
            prompt = self._config.get("prompts", {}).get(name, "")
            if prompt and kwargs:
                prompt = prompt.format(**kwargs)
            return prompt

    def get_all(self) -> dict:
        """Return a deep copy of the entire config."""
        with self._lock:
            import copy
            return copy.deepcopy(self._config)

    @property
    def server_url(self) -> str:
        return self.get("server", "url", default="http://localhost:7890")

    @property
    def model_lite(self) -> str:
        return self.get("models", "lite_model", default="deepseek-chat")

    @property
    def model_pro(self) -> str:
        return self.get("models", "pro_model", default="deepseek-chat")

    @property
    def model_max(self) -> str:
        return self.get("models", "max_model", default="deepseek-reasoner")

    @property
    def provider(self) -> str:
        return self.get("models", "provider", default="anthropic")


# Global singleton
_config_manager: ConfigManager | None = None
_config_lock = threading.Lock()


def get_config_manager() -> ConfigManager:
    global _config_manager
    with _config_lock:
        if _config_manager is None:
            _config_manager = ConfigManager()
        return _config_manager
