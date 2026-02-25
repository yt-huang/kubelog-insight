# K8s 日志分析工具 — PROJECT KNOWLEDGE BASE

**Generated:** 2026-02-24
**Stack:** Python 3.8+ · Tkinter · kubectl / kubectl-ai · ReportLab (optional)

---

## OVERVIEW

A Kubernetes log analysis tool that wraps `kubectl` log extraction → preprocessing → `kubectl-ai` AI analysis into a pipeline. Has both a Tkinter GUI (`main.py`) and a headless CLI (`run_analysis_cli.py`).

---

## STRUCTURE

```
.
├── main.py                # GUI entry — thin shim, imports gui.app.main()
├── run_analysis_cli.py    # CLI entry — argparse, calls analysis_engine.run_analysis()
├── requirements.txt       # Only reportlab>=4.0.0 (Tkinter is stdlib)
├── gui/
│   ├── __init__.py
│   └── app.py             # Tkinter MainWindow + threading + highlight logic
└── k8s_log_analyzer/
    ├── __init__.py        # Exports nothing explicitly
    ├── analysis_engine.py # Pipeline orchestrator: extract→preprocess→analyze
    ├── log_extractor.py   # kubectl subprocess calls, pod selector resolution
    ├── preprocessor.py    # Regex filter, head/tail/priority sampling, gzip
    ├── api_layer.py       # kubectl-ai subprocess wrapper + backend dispatch
    ├── history_store.py   # JSON file store at ~/.config/k8s-log-analyzer/history/
    └── pdf_report.py      # ReportLab PDF generation (lazy import)
```

---

## WHERE TO LOOK

| Task | Location |
|------|----------|
| Add new analysis pipeline step | `k8s_log_analyzer/analysis_engine.py:run_analysis()` |
| Add new AI backend (e.g. OpenAI) | `k8s_log_analyzer/api_layer.py:analyze_with_backend()` |
| Change GUI layout/fields | `gui/app.py:MainWindow._build_ui()` |
| Change highlight keywords | `gui/app.py:HIGHLIGHT_KEYWORDS` list |
| Change default preprocess config | `k8s_log_analyzer/preprocessor.py:PreprocessConfig` defaults |
| Change history storage path | `k8s_log_analyzer/history_store.py:_history_dir()` |
| Change PDF content/layout | `k8s_log_analyzer/pdf_report.py` |
| Change prompt sent to kubectl-ai | `k8s_log_analyzer/api_layer.py:run_kubectl_ai()` |
| CLI arguments | `run_analysis_cli.py:main()` |

---

## PIPELINE FLOW

```
run_analysis()  [analysis_engine.py]
  ↓ ExtractParams → extract_logs()  [log_extractor.py]
      kubectl get <type> → jsonpath selector → kubectl logs -l <selector>
  ↓ PreprocessConfig → preprocess()  [preprocessor.py]
      filter_by_patterns() → sample_lines() (priority lines + head/tail)
  ↓ AnalysisRequest → analyze_with_backend()  [api_layer.py]
      kubectl-ai --quiet < prompt+log_content (stdin pipe, 120s timeout)
  → AnalysisResult (dataclass)
```

---

## KEY DATACLASSES

| Class | File | Fields |
|-------|------|--------|
| `ExtractParams` | `log_extractor.py` | component_type, name, namespace, since, tail_lines, container |
| `PreprocessConfig` | `preprocessor.py` | include_patterns, exclude_patterns, priority_keywords, max_lines, use_gzip |
| `AnalysisRequest` | `api_layer.py` | log_content, component_type, component_name, namespace, time_range, prompt_extra |
| `AnalysisResult` | `analysis_engine.py` | success, raw_log_preview, preprocessed_log_preview, analysis_text, error_message, ... |
| `HistoryEntry` | `history_store.py` | timestamp, component_type, component_name, namespace, success, analysis_text, id |

---

## CONVENTIONS

- **Error returns**: All I/O functions return `Tuple[str, str]` = `(result, error_message)`. Empty error = success.
- **Lazy imports**: ReportLab imported inside `_get_reportlab()` — returns `None` if not installed. Always check before calling PDF functions.
- **Subprocess timeouts**: `kubectl logs` = 300s, `kubectl-ai` = 120s, `kubectl get` = 30s.
- **Log size cap**: `api_layer.py` hard-caps input at `120_000` chars before sending to kubectl-ai.
- **Preview cap**: `analysis_engine.py` stores only first 2000 chars as preview in result.
- **History IDs**: Format `YYYYMMDD-HHMMSS[-N]` (UTC), stored as `~/.config/k8s-log-analyzer/history/<id>.json`.
- **GUI threading**: Analysis runs in `threading.Thread(daemon=True)`. GUI updates via `root.after(0, ...)` — never update Tkinter widgets from worker thread directly.
- **sys.path hack**: Both `main.py` and `gui/app.py` prepend project root to `sys.path`. Expected behavior for non-installed usage.

---

## ANTI-PATTERNS (THIS PROJECT)

- **DO NOT** call `kubectl-ai` with streaming — invoked via `subprocess.run()` with full stdout capture; no streaming support.
- **DO NOT** update Tkinter widgets directly from background threads — always use `root.after(0, callback)`.
- **DO NOT** pass raw (unpreprocessed) logs to `analyze_with_backend()` — always preprocess first.
- **DO NOT** add mandatory `reportlab` usage — it's optional; use `_get_reportlab()` and handle `None`.
- **DO NOT** use `history_store.py` for large log storage — only previews (first 1000 chars) are persisted.

---

## COMMANDS

```bash
# GUI
python main.py
python -m gui.app

# CLI
python run_analysis_cli.py --type deployment --name nginx --namespace default --since 1h
python run_analysis_cli.py --type statefulset --name redis --since 30m --tail 2000 --no-save

# Install optional PDF dependency
pip install reportlab>=4.0.0

# Setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

---

## NOTES

- No test suite (no `*_test.py`, no `pytest.ini`, no `pyproject.toml`).
- `k8s_log_analyzer/__init__.py` is empty — import modules directly.
- `component_type` must be lowercase `"deployment"` or `"statefulset"` — validated in `log_extractor.py`.
- `PreprocessConfig.priority_keywords` default: `["exception", "error", "panic", "fatal", "nullpointer", "npe"]` — lines matching these are always kept during sampling.
- Backend dispatch in `api_layer.py` has a stub for future backends (`"deepseek"` mentioned in docstring) — add new backends in `analyze_with_backend()`.
- History sorted by file mtime (newest first), limited to 100 entries by default.
