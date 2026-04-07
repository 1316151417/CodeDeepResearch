"""
EventBus for pipeline-side event publishing.
Publishes events locally and via HTTP to the Flask dashboard.
"""
import json
import threading
import time
import queue
from datetime import datetime

import requests

from monitor.events import PipelineEvent, PipelineEventType


class EventBus:
    """
    Pipeline端的事件总线。

    publish() 将事件：
    1. 追加到本地 _local_buffer（pipeline结束后flush到run文件）
    2. 异步POST到Flask server（非阻塞，失败降级为local_only）

    两个进程通过HTTP通信，pipeline是发布者，Flask是订阅者。
    """

    def __init__(self, server_url: str = "http://localhost:7890"):
        self._server_url = server_url.rstrip("/")
        self._local_buffer: list[PipelineEvent] = []
        self._local_only = False
        self._last_retry = 0
        self._retry_interval = 30  # 每30秒重试一次连接

    def publish(self, event: PipelineEvent) -> None:
        """Publish an event to all subscribers."""
        # 1. Always append to local buffer
        self._local_buffer.append(event)

        # 2. Try HTTP POST if not in local_only mode
        if not self._local_only:
            self._try_post(event)

    def _try_post(self, event: PipelineEvent) -> None:
        """Attempt to POST event to Flask server. Fail silently on timeout."""
        try:
            resp = requests.post(
                f"{self._server_url}/api/events",
                json=event.to_dict(),
                timeout=2,
            )
            if resp.status_code != 200:
                self._maybe_switch_to_local()
        except requests.exceptions.Timeout:
            self._maybe_switch_to_local()
        except requests.exceptions.ConnectionError:
            self._maybe_switch_to_local()
        except Exception:
            self._maybe_switch_to_local()

    def _maybe_switch_to_local(self) -> None:
        """Switch to local-only mode if enough time has passed since last retry."""
        now = time.time()
        if now - self._last_retry < self._retry_interval:
            return
        self._last_retry = now
        # Don't switch to local_only permanently - just skip this post
        # and retry next time. The Flask may have started.

    def get_local_buffer(self) -> list[PipelineEvent]:
        """Get a copy of all locally buffered events."""
        return list(self._local_buffer)

    def clear_buffer(self) -> None:
        """Clear the local buffer (called after flush to file)."""
        self._local_buffer.clear()

    @property
    def is_local_only(self) -> bool:
        return self._local_only

    def check_server(self) -> bool:
        """Check if the Flask server is reachable."""
        try:
            resp = requests.get(f"{self._server_url}/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False


# Global singleton
_event_bus: EventBus | None = None
_event_bus_lock = threading.Lock()


def get_event_bus(server_url: str = "http://localhost:7890") -> EventBus:
    global _event_bus
    with _event_bus_lock:
        if _event_bus is None:
            _event_bus = EventBus(server_url=server_url)
        return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (useful for testing)."""
    global _event_bus
    with _event_bus_lock:
        _event_bus = None
