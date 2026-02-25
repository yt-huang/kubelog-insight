#!/usr/bin/env python3
"""
命令行方式运行一次分析（无需 GUI）。
示例:
  python run_analysis_cli.py --type deployment --name nginx --namespace default --since 1h
  python run_analysis_cli.py --type deployment --name nginx --llm-provider openai --model gpt-4o
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from k8s_log_analyzer.analysis_engine import run_analysis
from k8s_log_analyzer.history_store import save_entry, HistoryEntry
from datetime import datetime


def main():
    p = argparse.ArgumentParser(description="K8s 日志分析（命令行）")
    p.add_argument("--type", "-t", choices=["deployment", "statefulset"], default="deployment", help="组件类型")
    p.add_argument("--name", "-n", required=True, help="组件名称")
    p.add_argument("--namespace", "-N", default="default", help="命名空间")
    p.add_argument("--since", "-s", default="1h", help="时间范围，如 1h, 30m, 24h")
    p.add_argument("--tail", type=int, default=5000, help="最多拉取行数")
    p.add_argument("--no-save", action="store_true", help="不写入历史记录")
    p.add_argument("--kubeconfig", "-k", help="kubeconfig 文件路径")
    p.add_argument("--api-key", help="API Key（不保存）")
    p.add_argument("--api-base", help="API Base URL")
    p.add_argument("--llm-provider", default="gemini", 
                  choices=["gemini", "openai", "azopenai", "grok", "ollama", "vertexai"],
                  help="LLM Provider (默认: gemini)")
    p.add_argument("--model", help="Model 名称（如 gpt-4o, gemini-2.0-flash）")
    args = p.parse_args()

    print("正在分析...")
    result = run_analysis(
        component_type=args.type,
        component_name=args.name,
        namespace=args.namespace,
        time_range=args.since,
        tail_lines=args.tail,
        backend="kubectl-ai",
        kubeconfig=args.kubeconfig,
        api_key=args.api_key,
        api_base_url=args.api_base,
        llm_provider=args.llm_provider,
        model=args.model,
    )

    if result.success:
        print("\n--- 分析结果 ---\n")
        print(result.analysis_text)
        if not args.no_save:
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
            print("\n(已保存到历史记录)")
    else:
        print("分析失败:", result.error_message, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
