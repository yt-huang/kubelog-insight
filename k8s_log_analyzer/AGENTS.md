# k8s_log_analyzer — PACKAGE KNOWLEDGE BASE

Core library. Pure Python, no framework. Imported by both `gui/app.py` and `run_analysis_cli.py`.

---

## OVERVIEW

Pipeline: `log_extractor` → `preprocessor` → `api_layer`, orchestrated by `analysis_engine`. Results persisted via `history_store`. PDF export via `pdf_report` (ReportLab optional).

---

## WHERE TO LOOK

| Task | File | Symbol |
|------|------|--------|
| Add pipeline step | `analysis_engine.py` | `run_analysis()` |
| Add AI backend | `api_layer.py` | `analyze_with_backend()` |
| Change prompt | `api_layer.py` | `run_kubectl_ai()` — inline string |
| Add filter keyword | `preprocessor.py` | `PreprocessConfig.priority_keywords` |
| Change sampling logic | `preprocessor.py` | `sample_lines()` |
| Support new component type | `log_extractor.py` | `extract_logs()` — extend `kind` check |
| Add history fields | `history_store.py` | `HistoryEntry` dataclass + all callers |
| Add PDF sections | `pdf_report.py` | `generate_analysis_pdf()` |

---

## MODULE RESPONSIBILITIES

- **`analysis_engine.py`** — Orchestrator only. No subprocess calls. Composes other modules. Returns `AnalysisResult`.
- **`log_extractor.py`** — Two subprocess calls: `kubectl get` (jsonpath selector) then `kubectl logs -l`. Supports Deployment + StatefulSet only.
- **`preprocessor.py`** — Pure Python (no subprocess). Regex + sampling. `use_gzip` field exists but gzip is never applied in the pipeline (only `compress_log`/`decompress_log` helpers exposed).
- **`api_layer.py`** — One subprocess call: `kubectl-ai --quiet` or `kubectl ai --quiet` (auto-detects binary). Stdin = constructed prompt + log content.
- **`history_store.py`** — JSON files at `~/.config/k8s-log-analyzer/history/`. One file per entry. No database.
- **`pdf_report.py`** — Lazy ReportLab import via `_get_reportlab()`. Returns `Optional[str]` (None=success, str=error).

---

## CONVENTIONS

- **Return pattern**: `Tuple[str, str]` = `(value, error)`. Non-empty error = failure. Used by: `extract_logs`, `run_kubectl_ai`, `analyze_with_backend`, `get_pod_selector`.
- **`AnalysisResult.success`**: Set `True` only at the very end of `run_analysis()` after all steps succeed.
- **Subprocess env**: `env=None` in `api_layer.py` — inherits parent environment (needed for `GOOGLE_API_KEY` / `GEMINI_API_KEY` env vars).
- **Dataclasses**: All config/params/results are `@dataclass`. Use `field(default_factory=...)` for mutable defaults.

---

## ANTI-PATTERNS

- **DO NOT** call `pdf_report` functions without checking return value — they return error strings, not exceptions.
- **DO NOT** store full logs in `HistoryEntry` — only `preprocessed_preview[:1000]` is expected by callers.
- **DO NOT** add mandatory top-level imports of `reportlab` — keep lazy via `_get_reportlab()`.
- **DO NOT** call `subprocess.run()` with `shell=True` — all subprocess calls use list args (safer).
- **DO NOT** skip `preprocess()` before `analyze_with_backend()` — raw logs may exceed the 120k char cap badly.
- **DO NOT** add new component types without updating the `kind not in (...)` guard in `log_extractor.py`.

---

## EXTENSION POINTS

**Add new AI backend:**
```python
# api_layer.py → analyze_with_backend()
if backend == "openai":
    return run_openai(request)  # implement run_openai()
```

**Add new preprocessing step:**
```python
# preprocessor.py → preprocess()
raw_log = my_new_step(raw_log, config)  # add after sample_lines()
```

**Add new component type:**
```python
# log_extractor.py → extract_logs()
kind = params.component_type.strip().lower()
if kind not in ("deployment", "statefulset", "daemonset"):  # extend here
    ...
```
