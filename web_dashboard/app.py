"""
web_dashboard/app.py

作用：
- 作为本地开发模式下启动 Web 管理系统的入口脚本。

实现方式：
- 直接复用 `web_dashboard` 包中的 `run_dev_server()`。

调用方式：
- python web_dashboard/app.py
"""

from web_dashboard import run_dev_server

if __name__ == "__main__":
    run_dev_server()
