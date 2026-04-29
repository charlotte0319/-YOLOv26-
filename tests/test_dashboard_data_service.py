"""
tests/test_dashboard_data_service.py

作用：
- 校验看板服务层的 CSV 读取、统计、筛选、分页和训练解析逻辑。

调用关系：
- 由 `pytest` 自动执行。
- 主要覆盖 `web_dashboard.data_service` 兼容门面导出的核心函数。
"""

from pathlib import Path

import pytest

from web_dashboard.data_service import (
    DashboardDataError,
    build_dashboard_page,
    build_model_report,
    build_record_analytics,
    build_records_page,
    build_row_entries,
    build_summary,
    build_system_status,
    derive_actual_row_count,
    enrich_record,
    normalize_thresholds,
    parse_training_results_csv,
    read_csv_data,
)


def test_build_summary_empty():
    summary = build_summary([], "yolo26n", "v1")
    assert summary["image_count"] == 0
    assert summary["version"] == "yolo26n-v1"


def test_build_summary_with_records():
    records = [
        {"product_count": 10, "empty_count": 5, "empty_ratio": 0.3333, "actual_rows": 3, "n_rows": 3, "row_capacity": 3, "file": "a.jpg"},
        {"product_count": 20, "empty_count": 0, "empty_ratio": 0.0, "actual_rows": 2, "n_rows": 2, "row_capacity": 2, "file": "b.jpg"},
    ]
    summary = build_summary(records, "yolo26n", "v1")
    assert summary["image_count"] == 2
    assert summary["total_product"] == 30
    assert summary["total_empty"] == 5
    assert summary["worst_image"] == "a.jpg"
    assert summary["max_rows_detected"] == 3
    assert summary["avg_product_per_image"] == 15.0


def test_normalize_thresholds_clamps_values():
    thresholds = normalize_thresholds(-5, 3)
    assert thresholds["mid"] == 0.0
    assert thresholds["high"] == 3.0


def test_normalize_thresholds_handles_nan():
    thresholds = normalize_thresholds(float("nan"), float("nan"))
    assert thresholds["mid"] == 10.0
    assert thresholds["high"] == 30.0


def test_derive_actual_row_count_with_gaps():
    record = {"n_rows": 2, "row_capacity": 5, "row4_empty": 1, "row4_product": 0}
    assert derive_actual_row_count(record) == 4


def test_derive_actual_row_count_empty():
    record = {"n_rows": 0}
    assert derive_actual_row_count(record) == 0


def test_build_row_entries_basic():
    record = {
        "n_rows": 2,
        "row_capacity": 2,
        "row1_product": 8,
        "row1_empty": 2,
        "row1_ratio": 0.2,
        "row2_product": 10,
        "row2_empty": 0,
        "row2_ratio": 0.0,
    }
    entries = build_row_entries(record)
    assert len(entries) == 2
    assert entries[0]["product_count"] == 8
    assert entries[0]["empty_count"] == 2
    assert entries[0]["empty_ratio"] == 0.2
    assert entries[1]["empty_count"] == 0


def test_enrich_record_adds_fields():
    record = {"n_rows": 1, "row_capacity": 1, "row1_product": 5, "row1_empty": 1, "row1_ratio": 0.1667}
    enriched = enrich_record(record)
    assert "actual_rows" in enriched
    assert "row_entries" in enriched
    assert "active_row_count" in enriched
    assert enriched["actual_rows"] == 1
    assert enriched["active_row_count"] == 1


def test_read_csv_data_real_file(tmp_path: Path):
    csv_path = tmp_path / "analysis_results.csv"
    csv_path.write_text(
        "file,product_count,empty_count,empty_ratio,n_rows,row_capacity,row1_product,row1_empty,row1_ratio,timestamp\n"
        "img1.jpg,10,2,0.1667,3,3,4,1,0.2,2026-03-31 10:00:00\n"
        "img2.jpg,20,0,0.0,2,2,7,0,0.0,2026-03-31 10:00:01\n",
        encoding="utf-8-sig",
    )
    records = read_csv_data(csv_path)
    assert len(records) == 2
    assert records[0]["product_count"] == 10
    assert records[0]["empty_count"] == 2
    assert isinstance(records[0]["empty_ratio"], float)
    assert isinstance(records[0]["row1_product"], int)
    assert isinstance(records[0]["row1_empty"], int)
    assert isinstance(records[0]["row1_ratio"], float)
    assert "row_entries" in records[0]


def test_read_csv_data_missing_file(tmp_path: Path):
    records = read_csv_data(tmp_path / "nonexistent.csv")
    assert records == []


def test_read_csv_data_empty_file(tmp_path: Path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("file,product_count,empty_count,empty_ratio\n", encoding="utf-8-sig")
    records = read_csv_data(csv_path)
    assert records == []


def test_read_csv_data_invalid_file_raises_dashboard_error(tmp_path: Path):
    csv_path = tmp_path / "broken.csv"
    csv_path.write_text(
        "file,product_count,empty_count,empty_ratio,n_rows,row_capacity,row1_product\n"
        "img1.jpg,not-a-number,2,0.1,2,2,5\n",
        encoding="utf-8-sig",
    )

    with pytest.raises(DashboardDataError):
        read_csv_data(csv_path)


def test_build_dashboard_page_applies_thresholds_and_filtering():
    records = [
        {"file": "a.jpg", "product_count": 10, "empty_count": 4, "empty_ratio": 0.4, "actual_rows": 3},
        {"file": "b.jpg", "product_count": 10, "empty_count": 1, "empty_ratio": 0.1, "actual_rows": 2},
        {"file": "c.jpg", "product_count": 10, "empty_count": 0, "empty_ratio": 0.02, "actual_rows": 1},
    ]
    payload = build_dashboard_page(records, "yolo26n", "v1", risk_filter="high", mid_threshold=5, high_threshold=20)
    assert payload["filtered_total"] == 1
    assert payload["records"][0]["file"] == "a.jpg"
    assert payload["records"][0]["risk_label"] == "高风险"


def test_build_dashboard_page_limit_truncates_overview_records():
    records = [
        {"file": "a.jpg", "product_count": 10, "empty_count": 4, "empty_ratio": 0.4, "actual_rows": 3},
        {"file": "b.jpg", "product_count": 10, "empty_count": 1, "empty_ratio": 0.1, "actual_rows": 2},
        {"file": "c.jpg", "product_count": 10, "empty_count": 0, "empty_ratio": 0.02, "actual_rows": 1},
    ]

    payload = build_dashboard_page(records, "yolo26n", "v1", limit=2)

    assert payload["record_total"] == 3
    assert payload["filtered_total"] == 3
    assert payload["displayed_total"] == 2
    assert payload["display_limit"] == 2
    assert payload["is_truncated"] is True
    assert len(payload["records"]) == 2


def test_build_records_page_paginates_and_sorts():
    records = [
        {"file": "a.jpg", "product_count": 5, "empty_count": 1, "empty_ratio": 0.1, "actual_rows": 1, "row_entries": []},
        {"file": "b.jpg", "product_count": 6, "empty_count": 2, "empty_ratio": 0.3, "actual_rows": 2, "row_entries": []},
        {"file": "c.jpg", "product_count": 7, "empty_count": 0, "empty_ratio": 0.0, "actual_rows": 3, "row_entries": []},
    ]
    payload = build_records_page(records, "yolo26n", "v1", page=1, per_page=2, sort_key="empty_ratio", sort_dir="desc")
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert len(payload["records"]) == 2
    assert payload["records"][0]["file"] == "b.jpg"


def test_build_system_status(tmp_path: Path):
    csv_path = tmp_path / "analysis.csv"
    csv_path.write_text("file\nexample.jpg\n", encoding="utf-8")
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    (image_dir / "example.jpg").write_text("x", encoding="utf-8")
    train_dir = tmp_path / "train"
    train_dir.mkdir()
    (train_dir / "results.png").write_text("x", encoding="utf-8")

    status = build_system_status(
        {"active_model_family": "yolo26n"},
        csv_path,
        image_dir,
        train_dir,
    )
    assert status["csv_exists"] is True
    assert status["image_dir_exists"] is True
    assert status["predict_image_count"] == 1
    assert status["train_asset_count"] == 1


def test_build_system_status_missing_dirs(tmp_path: Path):
    status = build_system_status(
        {},
        tmp_path / "missing.csv",
        tmp_path / "no_images",
        tmp_path / "no_train",
    )
    assert status["csv_exists"] is False
    assert status["image_dir_exists"] is False
    assert status["predict_image_count"] == 0
    assert status["train_asset_count"] == 0


def test_parse_training_results_csv(tmp_path: Path):
    csv_path = tmp_path / "results.csv"
    csv_path.write_text(
        "epoch,time,train/box_loss,train/cls_loss,train/dfl_loss,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B),val/box_loss,val/cls_loss,val/dfl_loss\n"
        "1,10,1.0,0.5,0.1,0.8,0.6,0.7,0.5,1.1,0.6,0.2\n"
        "2,20,0.8,0.4,0.1,0.9,0.75,0.8,0.65,0.9,0.5,0.2\n",
        encoding="utf-8",
    )

    metrics = parse_training_results_csv(csv_path)
    assert metrics["exists"] is True
    assert metrics["latest_epoch"] == 2
    assert metrics["best_epoch"] == 2
    assert metrics["f1"] > 0


def test_parse_training_results_csv_missing(tmp_path: Path):
    metrics = parse_training_results_csv(tmp_path / "nonexistent.csv")
    assert metrics["exists"] is False
    assert metrics["map50_95"] == 0.0


def test_parse_training_results_csv_handles_invalid_numeric_values(tmp_path: Path):
    csv_path = tmp_path / "results_invalid.csv"
    csv_path.write_text(
        "epoch,time,train/box_loss,train/cls_loss,train/dfl_loss,metrics/precision(B),metrics/recall(B),metrics/mAP50(B),metrics/mAP50-95(B),val/box_loss,val/cls_loss,val/dfl_loss\n"
        "bad,xx,?,none,abc,nan_text,err,map,broken,v1,v2,v3\n",
        encoding="utf-8",
    )

    metrics = parse_training_results_csv(csv_path)
    assert metrics["exists"] is True
    assert metrics["latest_epoch"] == 0
    assert metrics["best_epoch"] == 0
    assert metrics["precision"] == 0.0
    assert metrics["map50_95"] == 0.0


def test_build_record_analytics_and_report():
    records = [
        {
            "file": "a.jpg",
            "timestamp": "2026-03-31 10:00:00",
            "product_count": 10,
            "empty_count": 2,
            "empty_ratio": 0.1667,
            "actual_rows": 5,
            "row_entries": [],
        },
        {
            "file": "b.jpg",
            "timestamp": "2026-03-31 10:00:01",
            "product_count": 20,
            "empty_count": 1,
            "empty_ratio": 0.0476,
            "actual_rows": 6,
            "row_entries": [],
        },
    ]
    analytics = build_record_analytics(records)
    summary = build_summary(records, "yolo26n", "v1")
    training_metrics = {"map50_95": 0.7, "precision": 0.8, "recall": 0.75}
    report = build_model_report(summary, training_metrics, {"primary_assets": ["results.png"], "curve_assets": ["BoxPR_curve.png"]})

    assert analytics["top_dense_cases"][0]["file"] == "b.jpg"
    assert report["primary_assets"] == ["results.png"]
    assert report["highlights"]


def test_build_record_analytics_empty():
    analytics = build_record_analytics([])
    assert analytics["top_empty_cases"] == []
    assert analytics["row_distribution"] == []


def test_build_record_analytics_handles_invalid_numeric_values():
    records = [
        {
            "file": "bad.jpg",
            "timestamp": "2026-03-31 10:00:00",
            "product_count": 1,
            "empty_count": 1,
            "empty_ratio": "bad-ratio",
            "actual_rows": "bad-rows",
            "row_entries": [],
        }
    ]

    analytics = build_record_analytics(records)
    assert analytics["top_empty_cases"][0]["file"] == "bad.jpg"
    assert analytics["top_empty_cases"][0]["empty_ratio"] == 0.0


def test_build_records_page_sorts_by_non_numeric_key_without_crash():
    """Sorting by a key whose value is a string should not crash."""
    records = [
        {"file": "a.jpg", "product_count": 5, "empty_count": 1, "empty_ratio": 0.1, "actual_rows": 1, "row_entries": [], "risk_label": "低风险"},
        {"file": "b.jpg", "product_count": 6, "empty_count": 2, "empty_ratio": 0.3, "actual_rows": 2, "row_entries": [], "risk_label": "高风险"},
    ]
    payload = build_records_page(records, "yolo26n", "v1", sort_key="risk_label", sort_dir="desc")
    assert "records" in payload
    assert payload["total"] == 2
