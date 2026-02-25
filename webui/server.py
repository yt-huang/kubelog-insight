from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename

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

    def _normalize_kind(raw: str) -> str:
        kind = (raw or "").strip().lower()
        if kind == "stateefulset":
            return "statefulset"
        return kind

    def _run_kubectl_list(args: List[str], kubeconfig: Optional[str] = None) -> Tuple[List[str], str]:
        env = os.environ.copy()
        if kubeconfig:
            env["KUBECONFIG"] = kubeconfig
        cmd = ["kubectl"] + args
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=30, env=env)
            if out.returncode != 0:
                return [], out.stderr.strip() or "kubectl command failed"
            lines = [line.strip() for line in out.stdout.splitlines() if line.strip()]
            return lines, ""
        except subprocess.TimeoutExpired:
            return [], "kubectl command timeout"
        except Exception as exc:
            return [], str(exc)

    def _validate_kubeconfig(kubeconfig: Optional[str]) -> Optional[str]:
        if not kubeconfig:
            return None
        path = Path(kubeconfig).expanduser()
        if path.is_dir():
            return f"kubeconfig 路径无效: {kubeconfig} 是目录，请选择具体文件"
        if not path.exists():
            return f"kubeconfig 文件不存在: {kubeconfig}"
        return None

    @app.get("/api/k8s/test-connection")
    def api_k8s_test_connection():
        kubeconfig = (request.args.get("kubeconfig") or "").strip() or None
        path_err = _validate_kubeconfig(kubeconfig)
        if path_err:
            return jsonify({"ok": False, "error": path_err}), 400
        env = os.environ.copy()
        if kubeconfig:
            env["KUBECONFIG"] = kubeconfig
        try:
            out = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )
            if out.returncode != 0:
                return jsonify({"ok": False, "error": out.stderr.strip() or "kubectl cluster-info failed"}), 400
            namespaces, err = _run_kubectl_list(
                ["get", "namespaces", "-o", "jsonpath={range .items[*]}{.metadata.name}{'\\n'}{end}"],
                kubeconfig=kubeconfig,
            )
            if err:
                return jsonify({"ok": False, "error": err}), 400
            return jsonify(
                {
                    "ok": True,
                    "message": "kubeconfig 连接成功",
                    "namespace_count": len(namespaces),
                }
            )
        except subprocess.TimeoutExpired:
            return jsonify({"ok": False, "error": "kubectl cluster-info timeout"}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.get("/api/k8s/namespaces")
    def api_k8s_namespaces():
        kubeconfig = (request.args.get("kubeconfig") or "").strip() or None
        path_err = _validate_kubeconfig(kubeconfig)
        if path_err:
            return jsonify({"ok": False, "error": path_err}), 400
        values, err = _run_kubectl_list(
            ["get", "namespaces", "-o", "jsonpath={range .items[*]}{.metadata.name}{'\\n'}{end}"],
            kubeconfig=kubeconfig,
        )
        if err:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True, "items": values})

    @app.get("/api/k8s/components")
    def api_k8s_components():
        raw_kind = request.args.get("component_type", "deployment")
        namespace = (request.args.get("namespace") or "default").strip()
        kubeconfig = (request.args.get("kubeconfig") or "").strip() or None
        path_err = _validate_kubeconfig(kubeconfig)
        if path_err:
            return jsonify({"ok": False, "error": path_err}), 400
        kind = _normalize_kind(raw_kind)
        if kind not in ("deployment", "statefulset", "daemonset"):
            return jsonify({"ok": False, "error": "component_type 必须是 deployment/statefulset/daemonset"}), 400
        values, err = _run_kubectl_list(
            ["get", kind, "-n", namespace, "-o", "jsonpath={range .items[*]}{.metadata.name}{'\\n'}{end}"],
            kubeconfig=kubeconfig,
        )
        if err:
            return jsonify({"ok": False, "error": err}), 400
        return jsonify({"ok": True, "items": values})

    @app.post("/api/analyze")
    def api_analyze():
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        component_type = _normalize_kind(payload.get("component_type") or "deployment")
        component_name = (payload.get("component_name") or "").strip()
        namespace = (payload.get("namespace") or "default").strip()
        time_range = (payload.get("time_range") or "").strip() or None
        kubeconfig = (payload.get("kubeconfig") or "").strip() or None
        api_key = (payload.get("api_key") or "").strip() or None
        api_base_url = (payload.get("api_base_url") or "").strip() or None
        llm_provider = (payload.get("llm_provider") or "openai").strip() or "openai"
        model = (payload.get("model") or "deepseek-chat").strip() or "deepseek-chat"
        if llm_provider == "openai" and not api_base_url:
            api_base_url = "https://api.deepseek.com"
        analysis_mode = (payload.get("analysis_mode") or "simple").strip() or "simple"
        try:
            tail_lines = int(payload.get("tail_lines", 5000))
        except (TypeError, ValueError):
            tail_lines = 5000
        try:
            max_iterations = int(payload.get("max_iterations", 50))
        except (TypeError, ValueError):
            max_iterations = 50

        if component_type not in ("deployment", "statefulset", "daemonset"):
            return jsonify({"ok": False, "error": "component_type 必须是 deployment/statefulset/daemonset"}), 400
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

    @app.post("/api/analyze-multi")
    def api_analyze_multi():
        payload: Dict[str, Any] = request.get_json(silent=True) or {}
        components = payload.get("components") or []
        if not isinstance(components, list) or not components:
            return jsonify({"ok": False, "error": "components 不能为空"}), 400

        time_range = (payload.get("time_range") or "").strip() or None
        kubeconfig = (payload.get("kubeconfig") or "").strip() or None
        api_key = (payload.get("api_key") or "").strip() or None
        api_base_url = (payload.get("api_base_url") or "").strip() or None
        llm_provider = (payload.get("llm_provider") or "openai").strip() or "openai"
        model = (payload.get("model") or "deepseek-chat").strip() or "deepseek-chat"
        if llm_provider == "openai" and not api_base_url:
            api_base_url = "https://api.deepseek.com"
        analysis_mode = (payload.get("analysis_mode") or "simple").strip() or "simple"
        try:
            tail_lines = int(payload.get("tail_lines", 5000))
        except (TypeError, ValueError):
            tail_lines = 5000
        try:
            max_iterations = int(payload.get("max_iterations", 50))
        except (TypeError, ValueError):
            max_iterations = 50

        results = []
        merged_text_parts = []
        success_count = 0

        for item in components:
            component_type = _normalize_kind((item or {}).get("component_type") or "deployment")
            namespace = ((item or {}).get("namespace") or "default").strip()
            component_name = ((item or {}).get("component_name") or "").strip()
            if component_type not in ("deployment", "statefulset", "daemonset"):
                results.append(
                    {
                        "success": False,
                        "component_type": component_type,
                        "component_name": component_name,
                        "namespace": namespace,
                        "error_message": "component_type 必须是 deployment/statefulset/daemonset",
                    }
                )
                continue
            if not component_name:
                results.append(
                    {
                        "success": False,
                        "component_type": component_type,
                        "component_name": component_name,
                        "namespace": namespace,
                        "error_message": "component_name 不能为空",
                    }
                )
                continue

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
            data = asdict(result)
            if result.success:
                success_count += 1
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
                data["history_id"] = save_entry(entry)
                merged_text_parts.append(
                    f"## {result.component_type}/{result.component_name} ({result.namespace})\n{result.analysis_text}"
                )
            else:
                data["history_id"] = ""
                merged_text_parts.append(
                    f"## {component_type}/{component_name} ({namespace})\n分析失败: {result.error_message}"
                )
            results.append(data)

        merged_text = "\n\n".join(merged_text_parts)
        return jsonify(
            {
                "ok": True,
                "summary": {
                    "total": len(components),
                    "success": success_count,
                    "failed": len(components) - success_count,
                },
                "merged_text": merged_text,
                "results": results,
            }
        )

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

    @app.post("/api/upload/kubeconfig")
    def api_upload_kubeconfig():
        file = request.files.get("file")
        if not file:
            return jsonify({"ok": False, "error": "未接收到文件"}), 400
        filename = secure_filename(file.filename or "kubeconfig")
        if not filename:
            filename = "kubeconfig"
        store_dir = Path.home() / ".config" / "k8s-log-analyzer" / "kubeconfigs"
        store_dir.mkdir(parents=True, exist_ok=True)
        target = store_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{filename}"
        file.save(target)
        return jsonify({"ok": True, "path": str(target)})

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

