from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, render_template, request

# Allow direct execution: python3 webui/server.py
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from k8s_log_analyzer.analysis_engine import AnalysisResult, run_analysis
from k8s_log_analyzer.history_store import (
    HistoryEntry,
    delete_entry,
    list_entries,
    load_entry,
    save_entry,
)
from k8s_log_analyzer.pdf_report import generate_analysis_pdf, generate_project_doc_pdf


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.post("/api/analyze")
    def api_analyze():
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        component_type = (payload.get("component_type") or "deployment").strip().lower()
        component_name = (payload.get("component_name") or "").strip()
        namespace = (payload.get("namespace") or "default").strip()
        time_range = (payload.get("time_range") or "").strip() or None
        kubeconfig = (payload.get("kubeconfig") or "").strip() or None
        api_key = (payload.get("api_key") or "").strip() or None
        api_base_url = (payload.get("api_base_url") or "").strip() or None
        llm_provider = (payload.get("llm_provider") or "gemini").strip() or "gemini"
        model = (payload.get("model") or "").strip() or None
        analysis_mode = (payload.get("analysis_mode") or "simple").strip() or "simple"
        try:
            tail_lines = int(payload.get("tail_lines", 5000))
        except (TypeError, ValueError):
            tail_lines = 5000
        try:
            max_iterations = int(payload.get("max_iterations", 50))
        except (TypeError, ValueError):
            max_iterations = 50

        if component_type not in ("deployment", "statefulset"):
            return jsonify({"ok": False, "error": "component_type 必须是 deployment 或 statefulset"}), 400
        if not component_name:
            return jsonify({"ok": False, "error": "component_name 不能为空"}), 400

        result = run_analysis(
            component_type=component_type,
            component_name=component_name,
            namespace=namespace,
            time_range=time_range,
            tail_lines=tail_lines,
            backend="kubectl-ai",
            kubeconfig=kubeconfig,
            api_key=api_key,
            api_base_url=api_base_url,
            llm_provider=llm_provider,
            model=model,
            max_iterations=max_iterations,
            analysis_mode=analysis_mode,
        )

        if result.success:
            entry = HistoryEntry(
                timestamp=datetime.now().isoformat(),
                component_type=result.component_type,
                component_name=result.component_name,
                namespace=result.namespace,
                time_range=result.time_range,
                success=True,
                analysis_text=result.analysis_text,
                error_message="",
                preprocessed_preview=result.preprocessed_log_preview[:1000],
            )
            entry_id = save_entry(entry)
        else:
            entry_id = ""

        data = asdict(result)
        data["history_id"] = entry_id
        return jsonify({"ok": True, "result": data})

    @app.get("/api/history")
    def api_history_list():
        entries = [asdict(e) for e in list_entries(limit=100)]
        return jsonify({"ok": True, "entries": entries})

    @app.get("/api/history/<entry_id>")
    def api_history_get(entry_id: str):
        entry = load_entry(entry_id)
        if not entry:
            return jsonify({"ok": False, "error": "未找到该历史记录"}), 404
        return jsonify({"ok": True, "entry": asdict(entry)})

    @app.delete("/api/history/<entry_id>")
    def api_history_delete(entry_id: str):
        if not delete_entry(entry_id):
            return jsonify({"ok": False, "error": "删除失败或记录不存在"}), 404
        return jsonify({"ok": True})

    @app.post("/api/export/project-pdf")
    def api_export_project_pdf():
        reports_dir = Path.home() / ".config" / "k8s-log-analyzer" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out = reports_dir / f"project-doc-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
        err = generate_project_doc_pdf(out)
        if err:
            return jsonify({"ok": False, "error": err}), 500
        return jsonify({"ok": True, "path": str(out)})

    @app.post("/api/export/analysis-pdf")
    def api_export_analysis_pdf():
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        result_data = payload.get("result") or {}
        reports_dir = Path.home() / ".config" / "k8s-log-analyzer" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        out = reports_dir / f"analysis-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"

        result = AnalysisResult(
            success=bool(result_data.get("success")),
            raw_log_preview=result_data.get("raw_log_preview", ""),
            preprocessed_log_preview=result_data.get("preprocessed_log_preview", ""),
            analysis_text=result_data.get("analysis_text", ""),
            error_message=result_data.get("error_message", ""),
            component_type=result_data.get("component_type", ""),
            component_name=result_data.get("component_name", ""),
            namespace=result_data.get("namespace", ""),
            time_range=result_data.get("time_range"),
        )
        err = generate_analysis_pdf(result, out)
        if err:
            return jsonify({"ok": False, "error": err}), 500
        return jsonify({"ok": True, "path": str(out)})

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="K8s 日志分析 Web UI")
    parser.add_argument("--host", default="127.0.0.1", help="Web 服务监听地址")
    parser.add_argument("--port", type=int, default=8787, help="Web 服务端口")
    parser.add_argument("--debug", action="store_true", help="开启 Flask debug")
    args = parser.parse_args()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()

