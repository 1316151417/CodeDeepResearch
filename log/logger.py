"""
Logger - formatted debug output for development.
"""
import json
import logging
import os

# Configure logger based on DEBUG environment variable or settings.json
_DEBUG_ENV = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")


def _get_debug() -> bool:
    """Lazy check: env var takes precedence, then settings.json."""
    if _DEBUG_ENV:
        return True
    try:
        from settings import load_settings
        return load_settings().get("debug", False)
    except Exception:
        return False


DEBUG = _get_debug()

# 禁止 httpx/httpcore 的 debug 日志（即使 DEBUG=1 也不打印 HTTP 请求日志）
for _lib in ("httpx", "httpcore", "openai", "anthropic", "urllib3"):
    _lg = logging.getLogger(_lib)
    _lg.setLevel(logging.WARNING)
    _lg.propagate = False


class Logger:
    """Simple debug logger that prints formatted output when DEBUG is enabled."""

    def debug(self, msg: str, start: str = "", end: str = "\n", flush: bool = False, **kwargs):
        if not DEBUG:
            return
        print(f"{start}{msg}", end=end, flush=flush)
        for key, value in kwargs.items():
            if value is None:
                continue
            if key == "messages":
                print(f"  {key}:")
                for i, m in enumerate(value):
                    role = m.get("role", "?")
                    content = m.get("content", "")
                    content_preview = content[:60] + "..." if len(content) > 60 else content
                    print(f"    [{i}] {role}: {content_preview}")
            elif key == "tools":
                print(f"  {key}:")
                for i, t in enumerate(value):
                    if hasattr(t, "name"):
                        print(f"    [{i}] {t.name}")
                        desc_line = t.description.split('\n')[0] if t.description else ""
                        print(f"        description: {desc_line}")
                        if t.parameters:
                            print(f"        parameters:")
                            for param_name, param in t.parameters.items():
                                print(f"          {param_name}: {param.description}")
                    else:
                        print(f"    [{i}] {t}")
            elif isinstance(value, str):
                preview = value[:100] + "..." if len(value) > 100 else value
                print(f"  {key}: {preview}")
            elif isinstance(value, (dict, list)):
                formatted = json.dumps(value, ensure_ascii=False, indent=2)
                preview = formatted[:200] + "..." if len(formatted) > 200 else formatted
                print(f"  {key}: {preview}")
            else:
                print(f"  {key}: {value}")


logger = Logger()
