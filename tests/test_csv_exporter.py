"""
tests/test_csv_exporter.py

作用：
- 校验 `inference_pipeline.csv_exporter` 的 CSV 导出行为。

调用关系：
- 由 `pytest` 自动执行。
- 覆盖导出成功路径与写入失败路径。
"""

import pytest

from inference_pipeline import csv_exporter


def test_export_csv(tmp_path):
    output = tmp_path / "out.csv"
    csv_exporter.CSV_PATH = output

    records = [
        {
            "file": "a.jpg",
            "product_count": 10,
            "empty_count": 2,
            "total": 12,
            "empty_ratio": 0.1667,
            "n_rows": 3,
            "max_rows_detected": 5,
            "row_capacity": 6,
        }
    ]

    csv_exporter.export_csv(records)
    assert output.exists()
    content = output.read_text(encoding="utf-8-sig")
    assert "file" in content
    assert "a.jpg" in content


def test_export_csv_supports_custom_output_path(tmp_path):
    csv_exporter.CSV_PATH = tmp_path / "default.csv"
    output = tmp_path / "nested" / "analysis_results.csv"

    records = [
        {
            "file": "legacy.jpg",
            "product_count": 8,
            "empty_count": 1,
            "total": 9,
            "empty_ratio": 0.1111,
            "n_rows": 2,
            "max_rows_detected": 2,
            "row_capacity": 3,
        }
    ]

    csv_exporter.export_csv(records, csv_path=output)

    assert output.exists()
    assert "legacy.jpg" in output.read_text(encoding="utf-8-sig")


def test_export_csv_raises_when_output_is_not_writable_directory(tmp_path):
    csv_exporter.CSV_PATH = tmp_path

    records = [
        {
            "file": "a.jpg",
            "product_count": 1,
            "empty_count": 0,
            "total": 1,
            "empty_ratio": 0.0,
            "n_rows": 1,
            "max_rows_detected": 1,
            "row_capacity": 2,
        }
    ]

    with pytest.raises(csv_exporter.CsvExportError):
        csv_exporter.export_csv(records)
