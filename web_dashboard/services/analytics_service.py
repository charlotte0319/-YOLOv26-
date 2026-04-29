"""
web_dashboard/services/analytics_service.py

作用：
- 基于预测记录构建案例分析页所需的统计结果与代表样本。

调用来源：
- `web_dashboard/__init__.py` 中的 `/api/cases` 路由调用 `build_cases_page()`。
- `web_dashboard/data_service.py` 作为兼容门面转发导出。

调用方式：
- `build_record_analytics(records, mid_threshold=..., high_threshold=...)`
- `build_cases_page(records, summary, snapshot, mid_threshold=..., high_threshold=...)`
"""

from __future__ import annotations

import math
from collections import Counter

from .records_service import attach_risk, normalize_thresholds


def _safe_float(value, default: float = 0.0) -> float:
    """安全转换为有限浮点数。"""
    try:
        numeric = float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def _safe_int(value, default: int = 0) -> int:
    """安全转换为整数。"""
    return int(_safe_float(value, float(default)))


def build_record_analytics(
    records: list[dict],
    *,
    mid_threshold: float = 10.0,
    high_threshold: float = 30.0,
) -> dict:
    """构建案例分析页需要的批次统计结果。"""
    thresholds = normalize_thresholds(mid_threshold, high_threshold)
    normalized_records = []
    for record in records:
        normalized = dict(record)
        normalized["empty_ratio"] = _safe_float(normalized.get("empty_ratio", 0.0), 0.0)
        normalized["actual_rows"] = _safe_int(normalized.get("actual_rows", normalized.get("n_rows", 0)), 0)
        normalized_records.append(normalized)

    tagged_records = [attach_risk(record, thresholds) for record in normalized_records]
    if not tagged_records:
        return {
            "row_distribution": [],
            "risk_distribution": [],
            "top_empty_cases": [],
            "top_dense_cases": [],
            "top_row_cases": [],
        }

    row_counter = Counter(_safe_int(record.get("actual_rows", record.get("n_rows", 0)), 0) for record in tagged_records)
    risk_counter = Counter(record.get("risk_class", "low") for record in tagged_records)

    def top_cases(key: str, limit: int = 6) -> list[dict]:
        # 对指定指标降序排序，抽取用于前端展示的 TopN 样本。
        ranked = sorted(tagged_records, key=lambda item: _safe_float(item.get(key, 0), 0.0), reverse=True)[:limit]
        return [
            {
                "file": item.get("file", ""),
                "timestamp": item.get("timestamp", ""),
                "product_count": int(item.get("product_count", 0)),
                "empty_count": int(item.get("empty_count", 0)),
                "empty_ratio": round(_safe_float(item.get("empty_ratio", 0), 0.0), 4),
                "actual_rows": _safe_int(item.get("actual_rows", item.get("n_rows", 0)), 0),
                "row_entries": item.get("row_entries", []),
                "risk_label": item.get("risk_label", ""),
                "risk_class": item.get("risk_class", ""),
            }
            for item in ranked
        ]

    return {
        "row_distribution": [
            {"row_count": row_count, "image_count": row_counter[row_count]}
            for row_count in sorted(row_counter)
        ],
        "risk_distribution": [
            {"risk_class": risk_class, "image_count": risk_counter[risk_class]}
            for risk_class in ("high", "mid", "low")
        ],
        "top_empty_cases": top_cases("empty_ratio"),
        "top_dense_cases": top_cases("product_count"),
        "top_row_cases": top_cases("actual_rows"),
    }


def build_cases_page(
    records: list[dict],
    summary: dict,
    snapshot: dict,
    *,
    mid_threshold: float = 10.0,
    high_threshold: float = 30.0,
) -> dict:
    """组合案例分析页面响应数据。"""
    return {
        "summary": summary,
        "snapshot": snapshot,
        "analytics": build_record_analytics(
            records,
            mid_threshold=mid_threshold,
            high_threshold=high_threshold,
        ),
        "thresholds": normalize_thresholds(mid_threshold, high_threshold),
    }
