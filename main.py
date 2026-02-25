#!/usr/bin/env python3
"""
K8s 日志分析工具入口。
默认启动 Web UI；可通过 --ui tkinter 回退到旧版 Tkinter 界面。
"""
import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    parser = argparse.ArgumentParser(description="K8s 日志分析工具")
    parser.add_argument("--ui", choices=["web", "tkinter"], default="web", help="选择 UI 类型")
    parser.add_argument("--host", default="127.0.0.1", help="Web UI 监听地址")
    parser.add_argument("--port", type=int, default=8787, help="Web UI 监听端口")
    parser.add_argument("--debug", action="store_true", help="开启 Web debug")
    args = parser.parse_args()

    if args.ui == "tkinter":
        from gui.app import main as tk_main

        tk_main()
        return

    from webui.server import create_app

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()
