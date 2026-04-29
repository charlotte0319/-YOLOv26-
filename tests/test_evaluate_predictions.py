"""
tests/test_evaluate_predictions.py

作用：
- 校验离线评估模块 `evaluation.evaluate_predictions` 的核心指标计算。

调用关系：
- 由 `pytest` 自动执行。
- 直接覆盖 `compute_metrics()` 的基础行为。
"""

from evaluation.evaluate_predictions import compute_metrics, to_float, to_int


def test_compute_metrics_basic():
    pred_records = [
        {
            "file": "a.jpg",
            "n_rows": "5",
            "empty_count": "2",
            "product_count": "10",
            "empty_ratio": "0.1667",
        },
        {
            "file": "b.jpg",
            "n_rows": "4",
            "empty_count": "1",
            "product_count": "8",
            "empty_ratio": "0.1111",
        },
    ]
    gt_records = [
        {
            "file": "a.jpg",
            "n_rows": "5",
            "empty_count": "3",
            "product_count": "10",
            "empty_ratio": "0.2300",
        },
        {
            "file": "b.jpg",
            "n_rows": "5",
            "empty_count": "1",
            "product_count": "7",
            "empty_ratio": "0.1250",
        },
    ]

    metrics = compute_metrics(pred_records, gt_records)
    assert metrics["matched_file_count"] == 2
    assert metrics["row_accuracy"] == 0.5
    assert metrics["row_mae"] == 0.5


def test_to_float_returns_default_on_bad_input():
    assert to_float("not_a_number") == 0.0
    assert to_float(None, 1.5) == 1.5


def test_to_int_returns_default_on_bad_input():
    assert to_int("not_a_number") == 0
    assert to_int(None, 42) == 42
