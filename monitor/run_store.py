"""
RunStore - manages pipeline run history as JSON files.
Pipeline process writes locally; Flask process reads via REST API.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from monitor.events import PipelineEvent


class RunStore:
    """
    Manages pipeline run history in .code_deep_research/runs/.

    Storage structure:
        .code_deep_research/runs/
            index.json              # run索引列表
            {run_id}.json           # 单个run的完整数据
    """

    def __init__(self, base_dir: str = ".code_deep_research/runs"):
        self._base = Path(base_dir)
        self._index_path = self._base / "index.json"
        self._lock = threading.Lock()
        self._current_run: dict | None = None
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        self._base.mkdir(parents=True, exist_ok=True)

    # ─── Pipeline-side write API ────────────────────────────────────────

    def start_run(self, run_id: str, metadata: dict) -> None:
        """Initialize a new run in memory."""
        with self._lock:
            self._current_run = {
                "run_id": run_id,
                "project_path": metadata.get("project_path", ""),
                "project_name": metadata.get("project_name", ""),
                "provider": metadata.get("provider", ""),
                "models": metadata.get("models", {}),
                "started_at": datetime.now().isoformat(),
                "ended_at": None,
                "total_duration_s": None,
                "status": "running",
                "events": [],
                "summary": {},
            }

    def append_event(self, event: PipelineEvent) -> None:
        """Append an event to the current run's event list (thread-safe)."""
        with self._lock:
            if self._current_run is not None:
                self._current_run["events"].append(event.to_dict())

    def finish_run(self, run_id: str, status: str, summary: dict) -> None:
        """Flush current run to JSON file and update index."""
        with self._lock:
            if self._current_run is None:
                return
            self._current_run["ended_at"] = datetime.now().isoformat()
            self._current_run["status"] = status
            self._current_run["summary"] = summary
            ended = datetime.now()
            started = datetime.fromisoformat(self._current_run["started_at"])
            self._current_run["total_duration_s"] = (ended - started).total_seconds()

            # Write run file
            run_path = self._base / f"{run_id}.json"
            with open(run_path, "w", encoding="utf-8") as f:
                json.dump(self._current_run, f, ensure_ascii=False, indent=2)

            # Update index
            self._update_index(self._current_run)
            self._current_run = None

    def _update_index(self, run: dict) -> None:
        """Add or update run in index.json."""
        index = self._load_index()
        # Remove existing entry with same run_id
        index["runs"] = [r for r in index["runs"] if r.get("run_id") != run["run_id"]]
        # Add new entry at front
        index["runs"].insert(0, {
            "run_id": run["run_id"],
            "project_name": run["project_name"],
            "project_path": run["project_path"],
            "status": run["status"],
            "started_at": run["started_at"],
            "ended_at": run["ended_at"],
            "total_duration_s": run["total_duration_s"],
        })
        # Keep last 100 runs
        index["runs"] = index["runs"][:100]
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def _load_index(self) -> dict:
        if self._index_path.exists():
            with open(self._index_path, encoding="utf-8") as f:
                return json.load(f)
        return {"runs": []}

    # ─── Flask-side read API ────────────────────────────────────────────

    def get_run(self, run_id: str) -> dict | None:
        """Load a specific run from disk."""
        run_path = self._base / f"{run_id}.json"
        if not run_path.exists():
            return None
        with open(run_path, encoding="utf-8") as f:
            return json.load(f)

    def list_runs(self, limit: int = 20) -> list[dict]:
        """Return recent runs from index (newest first)."""
        index = self._load_index()
        return index["runs"][:limit]

    def get_run_events(self, run_id: str) -> list[dict]:
        """Load events for a specific run."""
        run = self.get_run(run_id)
        if run is None:
            return []
        return run.get("events", [])


# Global singleton (used by Flask process)
_run_store: RunStore | None = None
_run_store_lock = threading.Lock()


def get_run_store(base_dir: str = ".code_deep_research/runs") -> RunStore:
    global _run_store
    with _run_store_lock:
        if _run_store is None:
            _run_store = RunStore(base_dir=base_dir)
        return _run_store
