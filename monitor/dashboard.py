"""
Flask dashboard server for pipeline monitoring.

Provides:
  - SSE stream at /sse
  - Event ingestion at /api/events (POST)
  - Run management at /api/runs/* (POST/GET)
  - Config management at /api/config (GET/POST)
  - Health check at /health

Run standalone:
    python -m monitor.dashboard
"""
import json
import threading
import time
import queue
from pathlib import Path

from flask import Flask, Response, jsonify, request, render_template

from monitor.events import PipelineEvent
from monitor.run_store import get_run_store, RunStore
from monitor.config_manager import get_config_manager, ConfigManager


def create_app(run_store: RunStore | None = None, config_manager: ConfigManager | None = None) -> Flask:
    app = Flask(__name__, template_folder="templates")

    # Use provided or global instances
    _run_store = run_store or get_run_store()
    _config = config_manager or get_config_manager()

    # SSE subscriber queues
    _sse_queues: list[queue.Queue] = []
    _sse_lock = threading.Lock()

    # ─── SSE Endpoint ──────────────────────────────────────────────────

    @app.route("/sse")
    def sse():
        """SSE stream: clients receive pipeline events in real-time."""
        q: queue.Queue = queue.Queue(maxsize=500)

        def generate():
            with _sse_lock:
                _sse_queues.append(q)
            try:
                while True:
                    try:
                        event = q.get(timeout=30)
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    except queue.Empty:
                        yield f": ping\n\n"
            except GeneratorExit:
                with _sse_lock:
                    if q in _sse_queues:
                        _sse_queues.remove(q)

        return Response(generate(), mimetype="text/event-stream")

    # ─── Broadcast helper ───────────────────────────────────────────────

    def _broadcast(event_dict: dict) -> None:
        with _sse_lock:
            for q in _sse_queues:
                try:
                    q.put_nowait(event_dict)
                except queue.Full:
                    pass  # Drop if client is slow

    # ─── Event Ingestion ───────────────────────────────────────────────

    @app.route("/api/events", methods=["POST"])
    def ingest_event():
        """Pipeline posts events here."""
        try:
            event_data = request.json
            event = PipelineEvent.from_dict(event_data)
            _run_store.append_event(event)
            _broadcast(event.to_dict())
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/api/runs/start", methods=["POST"])
    def start_run():
        """Pipeline announces a new run has started."""
        try:
            data = request.json
            run_id = data.get("run_id")
            metadata = data.get("metadata", {})
            _run_store.start_run(run_id, metadata)
            # Also notify current SSE clients
            _broadcast({
                "event_id": "announce",
                "type": "run_started",
                "data": {"run_id": run_id, "project_name": metadata.get("project_name", "")},
            })
            return jsonify({"status": "ok", "run_id": run_id})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    @app.route("/api/runs/<run_id>/finish", methods=["POST"])
    def finish_run(run_id: str):
        """Pipeline signals run completion."""
        try:
            data = request.json
            status = data.get("status", "completed")
            summary = data.get("summary", {})
            _run_store.finish_run(run_id, status, summary)
            _broadcast({
                "event_id": "announce",
                "type": "run_finished",
                "data": {"run_id": run_id, "status": status},
            })
            return jsonify({"status": "ok"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 400

    # ─── Run History ────────────────────────────────────────────────────

    @app.route("/api/runs")
    def list_runs():
        return jsonify(_run_store.list_runs(limit=20))

    @app.route("/api/runs/<run_id>")
    def get_run(run_id: str):
        run = _run_store.get_run(run_id)
        if run is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(run)

    @app.route("/api/runs/<run_id>/events")
    def get_run_events(run_id: str):
        return jsonify(_run_store.get_run_events(run_id))

    # ─── Config ────────────────────────────────────────────────────────

    @app.route("/api/config")
    def get_config():
        return jsonify(_config.get_all())

    @app.route("/api/config/reload", methods=["POST"])
    def reload_config():
        _config.reload()
        return jsonify({"status": "reloaded", "config": _config.get_all()})

    @app.route("/api/config/prompt/<name>", methods=["GET"])
    def get_prompt(name: str):
        """Get a specific prompt template (raw, for editing)."""
        prompt = _config.get("prompts", {}).get(name, "")
        return jsonify({"name": name, "content": prompt})

    @app.route("/api/config/prompt/<name>", methods=["POST"])
    def save_prompt(name: str):
        """Save a prompt template."""
        content = request.json.get("content", "")
        with _config._lock:
            if "prompts" not in _config._config:
                _config._config["prompts"] = {}
            _config._config["prompts"][name] = content
        # Write to disk
        if _config._config_path:
            import yaml
            with open(_config._config_path, "w", encoding="utf-8") as f:
                yaml.dump(_config._config, f, allow_unicode=True, default_flow_style=False)
        return jsonify({"status": "saved"})

    # ─── Dashboard UI ──────────────────────────────────────────────────

    @app.route("/")
    def index():
        return render_template("dashboard.html")

    # ─── Health ────────────────────────────────────────────────────────

    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "timestamp": time.time()})

    return app


def main():
    app = create_app()
    app.run(host="0.0.0.0", port=7890, debug=False, threaded=True)


if __name__ == "__main__":
    main()
