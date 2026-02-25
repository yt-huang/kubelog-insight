# gui — PACKAGE KNOWLEDGE BASE

Tkinter GUI package. Single meaningful file: `app.py` (308 lines). `__init__.py` is empty.

---

## OVERVIEW

`MainWindow` class wraps the full UI: input fields → analysis trigger → result display (with keyword highlight) → PDF export → history browser. Analysis runs in a daemon thread; all widget updates go through `root.after(0, callback)`.

---

## WHERE TO LOOK

| Task | Symbol |
|------|--------|
| Add input field | `MainWindow._build_ui()` — `input_frame` section |
| Change highlight keywords | Module-level `HIGHLIGHT_KEYWORDS` list |
| Change highlight color | `result_text.tag_configure("highlight", ...)` in `_build_ui()` |
| Change result display | `MainWindow._show_result()` |
| Change history display format | `MainWindow._refresh_history()` — the `label` string |
| Add button | `btn_row` frame in `_build_ui()` |
| Add new PDF export | Add `ttk.Button` + handler calling `pdf_report.*` |

---

## THREADING PATTERN

```python
# CORRECT: analysis in daemon thread
t = threading.Thread(target=task, daemon=True)
t.start()

# CORRECT: update widget from worker
self.root.after(0, lambda: self.status_var.set(msg))

# WRONG: direct widget update from thread
self.status_var.set(msg)  # DO NOT — Tkinter is not thread-safe
```

The `run_analysis_thread()` module-level function wraps this pattern. Use it for any new background operations.

---

## HIGHLIGHT SYSTEM

`tag_highlights(text_widget, start, end)` — scans text widget content with compiled regex, applies `"highlight"` tag (red bg/fg). Called with `text_widget.after(50, ...)` delay to ensure widget has rendered.

To add new keywords: append to `HIGHLIGHT_KEYWORDS`. They're compiled into one `|`-joined pattern.

---

## CONVENTIONS

- `_result: Optional[AnalysisResult]` — stores last successful result for PDF export. Check `if not self._result` before PDF operations.
- History uses `self._history_ids: list[str]` in sync with `self.history_list` Listbox. Index alignment is critical — refresh both together in `_refresh_history()`.
- Status label bound to `tk.StringVar(self.status_var)` — set via `self.status_var.set(...)`.
- Button disable during analysis: `self.btn_run.state(["disabled"])` / `["!disabled"]`.

---

## ANTI-PATTERNS

- **DO NOT** block the main thread with long operations — use `run_analysis_thread()`.
- **DO NOT** update `self.history_list` without also updating `self._history_ids` (must stay index-aligned).
- **DO NOT** call `generate_analysis_pdf()` without a saved `self._result` — check first.
- **DO NOT** add `sys.path` manipulation outside the existing block at module top (already handled).
