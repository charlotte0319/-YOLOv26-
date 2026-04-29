"""
tests/test_dashboard_app.py

作用：
- 校验 Flask 页面路由、API 结构、错误处理和 WSGI 启动顺序。

调用关系：
- 由 `pytest` 自动执行。
- 覆盖 `web_dashboard.create_app()` 生成应用后的核心接口行为。
"""

import importlib
import sys

import pytest

import project_config
import web_dashboard
from web_dashboard import create_app
from web_dashboard.services import DashboardDataError

PAGE_ROUTES = ["/", "/records", "/training", "/cases", "/system"]
API_ROUTES = [
    "/api/dashboard",
    "/api/records",
    "/api/cases",
    "/api/system",
    "/api/training",
]


def test_healthz_endpoint():
    app = create_app()
    client = app.test_client()

    response = client.get("/healthz")
    assert response.status_code in {200, 503}
    payload = response.get_json()
    assert payload["status"] in {"ok", "degraded"}
    assert "system" in payload


def test_page_routes_render_successfully():
    app = create_app()
    client = app.test_client()

    for route in PAGE_ROUTES:
        response = client.get(route)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "货架空缺管理系统" in body
        assert 'type="module"' in body


def test_api_routes_render_successfully():
    app = create_app()
    client = app.test_client()

    for route in API_ROUTES:
        response = client.get(route)
        assert response.status_code == 200


def test_dashboard_api_returns_page_payload():
    app = create_app()
    client = app.test_client()

    payload = client.get("/api/dashboard?mid=12&high=35").get_json()

    assert "summary" in payload
    assert "records" in payload
    assert "snapshot" in payload
    assert payload["thresholds"]["mid"] == 12.0
    assert payload["thresholds"]["high"] == 35.0


def test_records_api_returns_pagination_shape():
    app = create_app()
    client = app.test_client()

    payload = client.get("/api/records?page=1&per_page=20&sort=empty_ratio&dir=desc").get_json()

    assert "records" in payload
    assert "page" in payload
    assert "total_pages" in payload
    assert payload["per_page"] == 20


@pytest.mark.parametrize("route", ["/api/cases", "/api/system", "/api/training"])
def test_page_apis_read_csv_only_once(monkeypatch, route):
    # 锁住回归：页面接口不应重复读取同一份 CSV。
    call_count = {"value": 0}

    def fake_read_csv_data(*_args, **_kwargs):
        call_count["value"] += 1
        return []

    monkeypatch.setattr(web_dashboard, "read_csv_data", fake_read_csv_data)

    app = create_app()
    client = app.test_client()

    response = client.get(route)

    assert response.status_code == 200
    assert call_count["value"] == 1


def test_legacy_dashboard_bundle_endpoint_removed():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/dashboard/bundle")
    assert response.status_code == 404


def test_missing_prediction_image_returns_json_404():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/image/not-found.jpg")
    assert response.status_code == 404
    payload = response.get_json()
    assert payload["status"] == 404
    assert payload["error"] == "Not Found"


def test_invalid_query_params_return_400_json():
    app = create_app()
    client = app.test_client()

    dashboard_response = client.get("/api/dashboard?mid=abc")
    assert dashboard_response.status_code == 400
    assert dashboard_response.get_json()["error"] == "Bad Request"

    records_response = client.get("/api/records?page=abc")
    assert records_response.status_code == 400
    assert records_response.get_json()["error"] == "Bad Request"


def test_dashboard_data_error_returns_500_json(monkeypatch):
    app = create_app()
    client = app.test_client()

    def fake_read_csv_data(*_args, **_kwargs):
        raise DashboardDataError("读取预测 CSV 失败：broken.csv")

    monkeypatch.setattr(web_dashboard, "read_csv_data", fake_read_csv_data)

    response = client.get("/api/dashboard")
    assert response.status_code == 500
    payload = response.get_json()
    assert payload["error"] == "Dashboard Data Error"
    assert "broken.csv" in payload["message"]


def test_prediction_image_path_traversal_blocked():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/image/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404

    response = client.get("/api/image/../../../etc/passwd")
    assert response.status_code == 404


def test_wsgi_initializes_project_before_creating_app(monkeypatch):
    events = []

    def fake_init_project(stage="train"):
        events.append(f"init:{stage}")

    def fake_create_app():
        events.append("create")
        return object()

    monkeypatch.setattr(project_config, "init_project", fake_init_project)
    monkeypatch.setattr(web_dashboard, "create_app", fake_create_app)
    sys.modules.pop("wsgi", None)

    module = importlib.import_module("wsgi")

    assert events == ["init:dashboard", "create"]
    assert module.app is not None
