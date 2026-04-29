"""
web_dashboard/__init__.py

作用：
- 提供货架空缺管理系统的 Flask 应用工厂。
- 暴露页面路由、按页面拆分的数据接口、训练产物读取接口和健康检查接口。

实现方式：
- 通过 `create_app()` 构建 Flask 实例。
- 所有页面复用 `templates/page.html`，但只渲染当前页面所需 DOM。
- 数据由 `web_dashboard.services` 分层处理，路由层只负责参数解析和响应封装。
- CSV 解析失败时返回明确的 JSON 错误，避免“静默没数据”。

调用方式：
- 开发模式：`python web_dashboard/app.py`
- WSGI 模式：`python wsgi.py`
"""

from __future__ import annotations

import logging
import math

from flask import Flask, abort, jsonify, render_template, request, send_file
from werkzeug.exceptions import BadRequest, HTTPException

from project_config import (
    ACTIVE_MODEL_FAMILY,
    CSV_PATH,
    DASHBOARD_DEBUG,
    DASHBOARD_HOST,
    DASHBOARD_PORT,
    DASHBOARD_RECORD_LIMIT,
    DASHBOARD_STATIC,
    DASHBOARD_TEMPLATE,
    NN_IMG_DIR,
    TRAIN_OUT_DIR,
    TRAIN_PREDICT_VERSION,
    init_project,
    runtime_snapshot,
)
from web_dashboard.services import (
    DashboardDataError,
    build_cases_page,
    build_dashboard_page,
    build_records_page,
    build_summary,
    build_system_page,
    build_system_status,
    build_training_page,
    normalize_thresholds,
    read_csv_data,
    safe_resolve_asset,
)

PAGE_TITLES = {
    "dashboard": "总览",
    "records": "检测记录",
    "training": "训练报告",
    "cases": "案例分析",
    "system": "系统状态",
}


def render_page(page_key: str):
    """渲染共用页面模板，并注入当前页面标识。"""
    return render_template(
        "page.html",
        page_key=page_key,
        page_title=PAGE_TITLES[page_key],
        nav_items=PAGE_TITLES,
    )


def _get_int_arg(name: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    """读取整数查询参数，并做边界收敛。"""
    raw_value = request.args.get(name)
    if raw_value in (None, ""):
        value = default
    else:
        try:
            value = int(raw_value)
        except (TypeError, ValueError) as exc:
            raise BadRequest(f"查询参数 {name} 必须是整数。") from exc

    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _get_float_arg(name: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    """读取浮点查询参数，并做边界收敛。"""
    raw_value = request.args.get(name)
    if raw_value in (None, ""):
        value = default
    else:
        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise BadRequest(f"查询参数 {name} 必须是数字。") from exc

    if not math.isfinite(value):
        raise BadRequest(f"查询参数 {name} 必须是有限数字。")
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _get_page_meta(records: list[dict] | None = None) -> dict:
    """返回所有页面共用的轻量头部信息。"""
    # 允许上层传入已读取记录，避免同一次请求中重复读取 CSV。
    source_records = read_csv_data() if records is None else records
    return {
        "summary": build_summary(source_records, ACTIVE_MODEL_FAMILY, TRAIN_PREDICT_VERSION),
        "snapshot": runtime_snapshot(),
    }


def create_app() -> Flask:
    """创建并配置 Flask 应用实例。"""
    app = Flask(
        __name__,
        template_folder=str(DASHBOARD_TEMPLATE),
        static_folder=str(DASHBOARD_STATIC),
    )
    app.config["JSON_AS_ASCII"] = False
    logger = logging.getLogger(__name__)

    @app.route("/")
    def dashboard_page():
        return render_page("dashboard")

    @app.route("/records")
    def records_page():
        return render_page("records")

    @app.route("/training")
    def training_page():
        return render_page("training")

    @app.route("/cases")
    def cases_page():
        return render_page("cases")

    @app.route("/system")
    def system_page():
        return render_page("system")

    @app.route("/api/dashboard")
    def api_dashboard():
        records = read_csv_data()
        return jsonify(
            {
                **build_dashboard_page(
                    records,
                    ACTIVE_MODEL_FAMILY,
                    TRAIN_PREDICT_VERSION,
                    keyword=request.args.get("search", ""),
                    risk_filter=request.args.get("risk", "all"),
                    mid_threshold=_get_float_arg("mid", 10.0, minimum=0.0, maximum=99.0),
                    high_threshold=_get_float_arg("high", 30.0, minimum=0.1, maximum=100.0),
                    limit=DASHBOARD_RECORD_LIMIT,
                ),
                "snapshot": runtime_snapshot(),
            }
        )

    @app.route("/api/records")
    def api_records():
        records = read_csv_data()
        return jsonify(
            {
                **build_records_page(
                    records,
                    ACTIVE_MODEL_FAMILY,
                    TRAIN_PREDICT_VERSION,
                    page=_get_int_arg("page", 1, minimum=1),
                    per_page=_get_int_arg("per_page", 40, minimum=1, maximum=200),
                    keyword=request.args.get("search", ""),
                    risk_filter=request.args.get("risk", "all"),
                    sort_key=request.args.get("sort", "default"),
                    sort_dir=request.args.get("dir", "desc"),
                    mid_threshold=_get_float_arg("mid", 10.0, minimum=0.0, maximum=99.0),
                    high_threshold=_get_float_arg("high", 30.0, minimum=0.1, maximum=100.0),
                ),
                "snapshot": runtime_snapshot(),
            }
        )

    @app.route("/api/cases")
    def api_cases():
        records = read_csv_data()
        meta = _get_page_meta(records)
        thresholds = normalize_thresholds(
            _get_float_arg("mid", 10.0, minimum=0.0, maximum=99.0),
            _get_float_arg("high", 30.0, minimum=0.1, maximum=100.0),
        )
        return jsonify(
            build_cases_page(
                records,
                meta["summary"],
                meta["snapshot"],
                mid_threshold=thresholds["mid"],
                high_threshold=thresholds["high"],
            )
        )

    @app.route("/api/data")
    def api_data():
        return jsonify(read_csv_data())

    @app.route("/api/summary")
    def api_summary():
        return jsonify(_get_page_meta()["summary"])

    @app.route("/api/system")
    def api_system():
        records = read_csv_data()
        meta = _get_page_meta(records)
        return jsonify(build_system_page(meta["summary"], meta["snapshot"], CSV_PATH, NN_IMG_DIR))

    @app.route("/api/training")
    def api_training():
        records = read_csv_data()
        meta = _get_page_meta(records)
        return jsonify(build_training_page(meta["summary"], meta["snapshot"]))

    @app.route("/api/image/<filename>")
    def get_prediction_image(filename: str):
        image_path = safe_resolve_asset(NN_IMG_DIR, filename)
        if image_path is None:
            abort(404)
        return send_file(str(image_path))

    @app.route("/api/train-asset/<filename>")
    def get_training_asset(filename: str):
        asset_path = safe_resolve_asset(TRAIN_OUT_DIR, filename)
        if asset_path is None:
            abort(404)
        return send_file(str(asset_path))

    @app.route("/healthz")
    def healthz():
        snapshot = runtime_snapshot()
        system = build_system_status(snapshot, CSV_PATH, NN_IMG_DIR, TRAIN_OUT_DIR)
        healthy = system["csv_exists"] and system["image_dir_exists"] and system["train_dir_exists"]
        status_code = 200 if healthy else 503
        return jsonify({"status": "ok" if healthy else "degraded", "system": system}), status_code

    @app.errorhandler(DashboardDataError)
    def handle_dashboard_data_error(error: DashboardDataError):
        """对 CSV 解析等数据层错误返回明确提示。"""
        logger.exception("管理系统数据读取失败：%s", error)
        if request.path.startswith("/api/") or request.path == "/healthz":
            return jsonify({"error": "Dashboard Data Error", "message": str(error), "status": 500}), 500
        return str(error), 500

    @app.errorhandler(HTTPException)
    def handle_http_error(error: HTTPException):
        """统一返回 JSON 错误，避免 API 出现默认 HTML。"""
        if request.path.startswith("/api/") or request.path == "/healthz":
            return jsonify({"error": error.name, "message": error.description, "status": error.code}), error.code
        return error

    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """记录未处理异常，并向 API 返回简洁错误消息。"""
        logger.exception("管理系统请求失败：%s %s", request.method, request.path)
        if request.path.startswith("/api/") or request.path == "/healthz":
            return jsonify({"error": "Internal Server Error", "message": "服务器内部错误，请查看日志。", "status": 500}), 500
        return "服务器内部错误，请查看日志。", 500

    return app


def run_dev_server() -> None:
    """以 Flask 开发模式启动管理系统。"""
    init_project(stage="dashboard")
    display_host = "127.0.0.1" if DASHBOARD_HOST in {"0.0.0.0", "::"} else DASHBOARD_HOST
    print(f"[看板] 开发服务启动中：http://{display_host}:{DASHBOARD_PORT} (listen: {DASHBOARD_HOST}:{DASHBOARD_PORT})")
    app = create_app()
    app.run(debug=DASHBOARD_DEBUG, host=DASHBOARD_HOST, port=DASHBOARD_PORT)
