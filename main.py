import argparse
import os
import subprocess
import sys
import time

from pipeline import run_pipeline


def _check_server(url: str = "http://localhost:7890/health") -> bool:
    try:
        import requests
        resp = requests.get(url, timeout=2)
        return resp.status_code == 200
    except Exception:
        return False


def _wait_server(url: str = "http://localhost:7890", timeout: int = 10) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _check_server(url):
            return True
        time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Code Deep Research - 自动化代码深度分析"
    )
    parser.add_argument(
        "project_path",
        help="要分析的项目路径",
    )
    parser.add_argument(
        "--settings",
        default=None,
        help="配置文件路径 (默认: 当前目录/settings.json)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出文件路径 (默认: 写入 report/ 目录)",
    )
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="启用监控（自动启动 dashboard server）",
    )
    parser.add_argument(
        "--dashboard-only",
        action="store_true",
        help="仅启动 dashboard server（不运行 pipeline）",
    )

    args = parser.parse_args()

    # Dashboard-only mode
    if args.dashboard_only:
        from monitor.dashboard import main as dashboard_main
        dashboard_main()
        return

    # Auto-start dashboard if --monitor
    server_process = None
    if args.monitor:
        if _check_server():
            print("  [monitor] Dashboard already running at http://localhost:7890")
        else:
            print("  [monitor] Starting dashboard server...")
            server_process = subprocess.Popen(
                [sys.executable, "-m", "monitor.dashboard"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if _wait_server():
                print("  [monitor] Dashboard started at http://localhost:7890")
            else:
                print("  [monitor] Warning: dashboard failed to start within 10s, continuing without monitor")
                server_process = None

    project_path = os.path.abspath(args.project_path)
    if not os.path.isdir(project_path):
        print(f"错误: {project_path} 不是有效目录")
        return 1

    report = run_pipeline(
        project_path=project_path,
        settings_path=args.settings,
        monitor=args.monitor,
    )

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\n报告已写入: {args.output}")

    # Don't kill the dashboard - let it keep running
    return 0


if __name__ == "__main__":
    exit(main())
