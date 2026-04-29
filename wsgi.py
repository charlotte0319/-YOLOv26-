"""
wsgi.py

作用：
- 为 Waitress / Gunicorn / 其他 WSGI 服务提供标准入口。
- 启动前显式完成项目初始化，避免与开发模式行为不一致。
- 直接执行 `python wsgi.py` 时，按 project_config.py 中的 Host / Port 启动 Waitress。
"""

from project_config import DASHBOARD_HOST, DASHBOARD_PORT, init_project
from web_dashboard import create_app

init_project(stage="dashboard")
app = create_app()


def main() -> None:
    """以 Waitress 启动本地 WSGI 服务。"""
    from waitress import serve

    display_host = "127.0.0.1" if DASHBOARD_HOST in {"0.0.0.0", "::"} else DASHBOARD_HOST
    print(f"[看板] 生产服务启动中：http://{display_host}:{DASHBOARD_PORT} (listen: {DASHBOARD_HOST}:{DASHBOARD_PORT})")
    serve(app, host=DASHBOARD_HOST, port=DASHBOARD_PORT)


if __name__ == "__main__":
    main()
