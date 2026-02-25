"""
Tkinter GUI: input params, run analysis, show results with highlight, history browser.
"""
from __future__ import annotations
import re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from datetime import datetime
from typing import List, Optional, Tuple
import threading

# Assume package is run from project root or PYTHONPATH includes project root
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from k8s_log_analyzer.analysis_engine import run_analysis, AnalysisResult
from k8s_log_analyzer.history_store import (
    HistoryEntry,
    save_entry,
    load_entry,
    list_entries,
    delete_entry,
)
from k8s_log_analyzer.pdf_report import generate_analysis_pdf, generate_project_doc_pdf
from k8s_log_analyzer.preprocessor import PreprocessConfig
from k8s_log_analyzer.config_store import load_settings, save_settings, Settings
from k8s_log_analyzer.api_layer import _test_kubectl_connection, LLM_PROVIDERS


# Keywords to highlight in result text (high-risk)
HIGHLIGHT_KEYWORDS = [
    "exception", "error", "panic", "fatal", "nullpointer", "npe",
    "oom", "out of memory", "failed", "critical", "warning",
]


def _compute_highlight_ranges(content: str) -> List[Tuple[int, int]]:
    """Compute (start, end) byte offsets for highlight keywords. Run in thread."""
    pattern = re.compile(
        "|".join(re.escape(k) for k in HIGHLIGHT_KEYWORDS),
        re.IGNORECASE,
    )
    return [(m.start(), m.end()) for m in pattern.finditer(content)]


def tag_highlights_async(text_widget: tk.Text, batch_size: int = 40) -> None:
    """
    Apply highlights in small batches via after(), so UI stays responsive (fix 点不动).
    Computes ranges in a background thread, then applies tags on main thread in batches.
    """
    content = text_widget.get("1.0", tk.END)
    if not content:
        return
    text_widget.tag_remove("highlight", "1.0", tk.END)
    ranges: List[Tuple[int, int]] = []

    def compute():
        nonlocal ranges
        ranges = _compute_highlight_ranges(content)

    def apply_batch(start_index: int):
        end_index = min(start_index + batch_size, len(ranges))
        for i in range(start_index, end_index):
            s, e = ranges[i]
            text_widget.tag_add("highlight", f"1.0+{s}c", f"1.0+{e}c")
        if end_index < len(ranges):
            text_widget.after(5, lambda: apply_batch(end_index))

    def on_computed():
        if ranges:
            apply_batch(0)
        else:
            apply_batch(0)  # no-op

    def run_thread():
        compute()
        text_widget.after(0, on_computed)

    threading.Thread(target=run_thread, daemon=True).start()


def run_analysis_thread(
    component_type: str,
    component_name: str,
    namespace: str,
    time_range: Optional[str],
    tail_lines: Optional[int],
    result_callback,
    status_callback,
    kubeconfig: Optional[str] = None,
    api_key: Optional[str] = None,
    api_base_url: Optional[str] = None,
    llm_provider: str = "gemini",
    model: Optional[str] = None,
    max_iterations: int = 50,
    analysis_mode: str = "simple",
):
    """Run analysis in background and call result_callback with AnalysisResult."""
    def task():
        try:
            status_callback("正在提取日志...")
            result = run_analysis(
                component_type=component_type,
                component_name=component_name,
                namespace=namespace,
                time_range=time_range or None,
                tail_lines=tail_lines or 5000,
                preprocess_config=PreprocessConfig(),
                backend="kubectl-ai",
                kubeconfig=kubeconfig,
                api_key=api_key,
                api_base_url=api_base_url,
                llm_provider=llm_provider,
                model=model,
                max_iterations=max_iterations,
                analysis_mode=analysis_mode,
            )
            result_callback(result)
        except Exception as e:
            result_callback(AnalysisResult(
                success=False,
                error_message=str(e),
                component_type=component_type,
                component_name=component_name,
                namespace=namespace,
                time_range=time_range,
            ))

    t = threading.Thread(target=task, daemon=True)
    t.start()


class MainWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("K8s 日志分析工具 (kubectl-ai)")
        self.root.geometry("900x750")
        self.root.minsize(600, 500)

        self._build_ui()
        self._load_config()
        self._result: Optional[AnalysisResult] = None

    def _load_config(self):
        """Load saved settings into UI."""
        settings = load_settings()
        if settings.kubeconfig_path:
            self.kubeconfig_path.set(settings.kubeconfig_path)
        if settings.api_base_url:
            self.api_base_url.set(settings.api_base_url)
        # Note: api_key is NOT loaded (security)

    def _save_config(self):
        """Save current settings (excluding api_key for security)."""
        settings = Settings(
            kubeconfig_path=self.kubeconfig_path.get() or None,
            api_base_url=self.api_base_url.get() or None,
        )
        save_settings(settings)

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # --- Config area ---
        config_frame = ttk.LabelFrame(main, text="⚙ 配置", padding=8)
        config_frame.pack(fill=tk.X, pady=(0, 8))

        # kubeconfig row
        config_row0 = ttk.Frame(config_frame)
        config_row0.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(config_row0, text="kubeconfig:").pack(side=tk.LEFT, padx=(0, 4))
        self.kubeconfig_path = tk.StringVar()
        self.kubeconfig_entry = ttk.Entry(config_row0, textvariable=self.kubeconfig_path, width=40)
        self.kubeconfig_entry.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(config_row0, text="浏览...", command=self._browse_kubeconfig).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(config_row0, text="测试连接", command=self._test_kubectl).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(config_row0, text="清除", command=lambda: self.kubeconfig_path.set("")).pack(side=tk.LEFT)

        # LLM Provider config row
        config_row_llm = ttk.Frame(config_frame)
        config_row_llm.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(config_row_llm, text="LLM Provider:").pack(side=tk.LEFT, padx=(0, 4))
        self.llm_provider = tk.StringVar(value="gemini")
        self.llm_provider_combo = ttk.Combobox(
            config_row_llm, 
            textvariable=self.llm_provider,
            values=list(LLM_PROVIDERS.keys()),
            width=12,
            state="readonly"
        )
        self.llm_provider_combo.pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(config_row_llm, text="Model:").pack(side=tk.LEFT, padx=(0, 4))
        self.model = tk.StringVar()
        self.model_entry = ttk.Entry(config_row_llm, textvariable=self.model, width=20)
        self.model_entry.pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(config_row_llm, text="(如 deepseek-chat, gpt-4o)").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(config_row_llm, text="Max迭代:").pack(side=tk.LEFT, padx=(0, 4))
        self.max_iterations = tk.StringVar(value="50")
        self.max_iterations_spin = ttk.Spinbox(config_row_llm, from_=5, to=100, textvariable=self.max_iterations, width=5)
        self.max_iterations_spin.pack(side=tk.LEFT)

        # API config row
        config_row1 = ttk.Frame(config_frame)
        config_row1.pack(fill=tk.X)
        ttk.Label(config_row1, text="API Base URL:").pack(side=tk.LEFT, padx=(0, 4))
        self.api_base_url = tk.StringVar()
        self.api_base_url_entry = ttk.Entry(config_row1, textvariable=self.api_base_url, width=30)
        self.api_base_url_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.api_base_url_entry.bind("<FocusOut>", lambda e: self._save_config())
        
        ttk.Label(config_row1, text="API Key:").pack(side=tk.LEFT, padx=(0, 4))
        self.api_key = tk.StringVar()
        self.api_key_entry = ttk.Entry(config_row1, textvariable=self.api_key, width=20, show="*")
        self.api_key_entry.pack(side=tk.LEFT)

        # --- Input area ---
        input_frame = ttk.LabelFrame(main, text="分析参数", padding=8)
        input_frame.pack(fill=tk.X, pady=(0, 8))

        row0 = ttk.Frame(input_frame)
        row0.pack(fill=tk.X)
        ttk.Label(row0, text="组件类型:").pack(side=tk.LEFT, padx=(0, 4))
        self.component_type = ttk.Combobox(row0, values=["deployment", "statefulset"], width=14, state="readonly")
        self.component_type.set("deployment")
        self.component_type.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(row0, text="组件名称:").pack(side=tk.LEFT, padx=(0, 4))
        self.component_name = ttk.Entry(row0, width=24)
        self.component_name.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(row0, text="命名空间:").pack(side=tk.LEFT, padx=(0, 4))
        self.namespace = ttk.Entry(row0, width=14)
        self.namespace.insert(0, "default")
        self.namespace.pack(side=tk.LEFT, padx=(0, 16))

        row1 = ttk.Frame(input_frame)
        row1.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(row1, text="分析模式:").pack(side=tk.LEFT, padx=(0, 4))
        self.analysis_mode = tk.StringVar(value="simple")
        self.analysis_mode_combo = ttk.Combobox(
            row1, textvariable=self.analysis_mode,
            values=["simple", "full_scan"],
            width=14, state="readonly"
        )
        self.analysis_mode_combo.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row1, text="(simple=简要 full_scan=全量扫描+统计)").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Label(row1, text="时间范围:").pack(side=tk.LEFT, padx=(0, 4))
        self.time_range = ttk.Entry(row1, width=10)
        self.time_range.insert(0, "1h")
        self.time_range.pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(row1, text="最多行数:").pack(side=tk.LEFT, padx=(0, 4))
        self.tail_lines = ttk.Entry(row1, width=8)
        self.tail_lines.insert(0, "5000")
        self.tail_lines.pack(side=tk.LEFT)

        btn_row = ttk.Frame(input_frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))
        self.btn_run = ttk.Button(btn_row, text="开始分析", command=self._on_run)
        self.btn_run.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_export_pdf = ttk.Button(btn_row, text="导出本次结果为 PDF", command=self._on_export_pdf)
        self.btn_export_pdf.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_project_pdf = ttk.Button(btn_row, text="生成项目文档 PDF", command=self._on_project_pdf)
        self.btn_project_pdf.pack(side=tk.LEFT, padx=(0, 8))
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(btn_row, textvariable=self.status_var).pack(side=tk.LEFT, padx=(16, 0))

        # --- Result area ---
        result_frame = ttk.LabelFrame(main, text="分析结果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.result_text = scrolledtext.ScrolledText(
            result_frame,
            wrap=tk.WORD,
            height=16,
            font=("Consolas", 10),
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        self.result_text.tag_configure("highlight", background="#ffcccc", foreground="#990000")

        # --- History ---
        hist_frame = ttk.LabelFrame(main, text="历史记录", padding=8)
        hist_frame.pack(fill=tk.X)

        hist_top = ttk.Frame(hist_frame)
        hist_top.pack(fill=tk.X)
        ttk.Button(hist_top, text="刷新历史", command=self._refresh_history).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(hist_top, text="查看选中", command=self._view_history_entry).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(hist_top, text="删除选中", command=self._delete_history_entry).pack(side=tk.LEFT)

        self.history_list = tk.Listbox(hist_frame, height=4, font=("Consolas", 9))
        self.history_list.pack(fill=tk.X, pady=(4, 0))
        self._history_ids: list[str] = []
        self._refresh_history()

    def _browse_kubeconfig(self):
        path = filedialog.askopenfilename(
            title="选择 kubeconfig 文件",
            filetypes=[("Kubeconfig", "*.yaml *.yml"), ("All files", "*.*")]
        )
        if path:
            self.kubeconfig_path.set(path)
            self._save_config()

    def _test_kubectl(self):
        """Test kubectl connection to cluster (uses current kubeconfig if set)."""
        self.status_var.set("正在测试 kubectl 连接...")
        self.root.update_idletasks()
        kubeconfig = self.kubeconfig_path.get() or None

        def task():
            output, err = _test_kubectl_connection(kubeconfig=kubeconfig)
            self.root.after(0, lambda: self._show_kubectl_result(output, err))

        threading.Thread(target=task, daemon=True).start()

    def _show_kubectl_result(self, output: str, err: str):
        """Show kubectl connection test result."""
        self.status_var.set("就绪")
        if err:
            messagebox.showerror("连接失败", f"kubectl 连接测试失败:\n{err}")
        else:
            messagebox.showinfo("连接成功", f"kubectl 已成功连接到集群!\n\n{output[:200]}...")

    def _on_run(self):
        ct = (self.component_type.get() or "").strip().lower()
        cn = (self.component_name.get() or "").strip()
        ns = (self.namespace.get() or "default").strip()
        tr = (self.time_range.get() or "").strip() or None
        try:
            tl = int((self.tail_lines.get() or "5000").strip())
        except ValueError:
            tl = 5000
        if not cn:
            messagebox.showwarning("参数错误", "请输入组件名称")
            return
        if ct not in ("deployment", "statefulset"):
            messagebox.showwarning("参数错误", "组件类型请选择 deployment 或 statefulset")
            return

        kubeconfig = self.kubeconfig_path.get() or None
        api_key = self.api_key.get() or None
        api_base_url = self.api_base_url.get() or None
        llm_provider = self.llm_provider.get() or "gemini"
        model = self.model.get() or None
        try:
            max_iter = int(self.max_iterations.get() or "50")
        except ValueError:
            max_iter = 50
        analysis_mode = (self.analysis_mode.get() or "simple").strip() or "simple"

        self._save_config()

        self.btn_run.state(["disabled"])
        self.btn_export_pdf.state(["disabled"])
        self.status_var.set("分析中...")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert(tk.END, "正在执行，请稍候...\n")
        self.root.update_idletasks()

        def on_done(result: AnalysisResult):
            self.root.after(0, lambda: self._show_result(result))

        def on_status(msg: str):
            self.root.after(0, lambda: self.status_var.set(msg))

        run_analysis_thread(
            ct, cn, ns, tr, tl, on_done, on_status,
            kubeconfig, api_key, api_base_url, llm_provider, model,
            max_iterations=max_iter, analysis_mode=analysis_mode,
        )

    def _show_result(self, result: AnalysisResult):
        self.btn_run.state(["!disabled"])
        self.btn_export_pdf.state(["!disabled"])
        self.status_var.set("就绪")
        self._result = result

        self.result_text.delete("1.0", tk.END)
        if result.success:
            self.result_text.insert(tk.END, result.analysis_text)
            self.result_text.after(80, lambda: tag_highlights_async(self.result_text))
            # Save to history
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
            save_entry(entry)
            self._refresh_history()
        else:
            self.result_text.insert(tk.END, f"分析失败: {result.error_message}")

    def _on_export_pdf(self):
        if not self._result:
            messagebox.showinfo("提示", "请先执行一次分析再导出")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=f"k8s-log-report-{datetime.now().strftime('%Y%m%d-%H%M')}.pdf",
        )
        if not path:
            return
        err = generate_analysis_pdf(self._result, path)
        if err:
            messagebox.showerror("导出失败", err)
        else:
            messagebox.showinfo("成功", f"已保存: {path}")

    def _on_project_pdf(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile="k8s-log-analyzer-project-doc.pdf",
        )
        if not path:
            return
        err = generate_project_doc_pdf(path)
        if err:
            messagebox.showerror("导出失败", err)
        else:
            messagebox.showinfo("成功", f"已保存: {path}")

    def _refresh_history(self):
        self.history_list.delete(0, tk.END)
        self._history_ids.clear()
        for e in list_entries(limit=50):
            label = f"[{e.timestamp[:19]}] {e.component_type}/{e.component_name} ({e.namespace})"
            self.history_list.insert(tk.END, label)
            self._history_ids.append(e.id)

    def _get_selected_entry_id(self) -> Optional[str]:
        sel = self.history_list.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx >= len(self._history_ids):
            return None
        return self._history_ids[idx]

    def _view_history_entry(self):
        eid = self._get_selected_entry_id()
        if not eid:
            messagebox.showinfo("提示", "请先选择一条历史记录")
            return
        entry = load_entry(eid)
        if not entry:
            messagebox.showerror("错误", "无法加载该记录")
            return
        self.result_text.delete("1.0", tk.END)
        if entry.success:
            self.result_text.insert(tk.END, entry.analysis_text)
            self.result_text.after(80, lambda: tag_highlights_async(self.result_text))
        else:
            self.result_text.insert(tk.END, f"错误: {entry.error_message}\n\n{entry.analysis_text}")

    def _delete_history_entry(self):
        eid = self._get_selected_entry_id()
        if not eid:
            messagebox.showinfo("提示", "请先选择一条历史记录")
            return
        if messagebox.askyesno("确认", "确定删除该条历史记录？"):
            delete_entry(eid)
            self._refresh_history()

    def run(self):
        self.root.mainloop()


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
