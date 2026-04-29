"""
web_dashboard/services/records_service.py

作用：
- 负责预测记录的汇总、风险分级、筛选、排序与分页。

实现方式：
- 将风险阈值、查询条件和分页参数集中在服务层处理。
- 返回前端可直接消费的数据结构，避免浏览器端重复推导。
- 对非法阈值或 NaN/inf 输入做收敛，保证页面逻辑稳定。

调用方式：
- `build_dashboard_page(records, model_family, version, ...)`
- `build_records_page(records, model_family, version, ...)`
"""

from __future__ import annotations

import math

DEFAULT_MID_THRESHOLD = 10.0
DEFAULT_HIGH_THRESHOLD = 30.0
DEFAULT_PER_PAGE = 40
MAX_PER_PAGE = 200


def _safe_float(value, default: float) -> float:
    """将阈值安全转换为有限浮点数。"""
    try:
        numeric = float(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        return default
    return numeric if math.isfinite(numeric) else default


def normalize_thresholds(mid: float | int | str | None, high: float | int | str | None) -> dict[str, float]:
    """规范化风险阈值，保证中/高分界合法。"""
    safe_mid = max(0.0, min(_safe_float(mid, DEFAULT_MID_THRESHOLD), 99.0))
    safe_high = max(safe_mid + 0.1, min(_safe_float(high, DEFAULT_HIGH_THRESHOLD), 100.0))
    return {
        "mid": round(safe_mid, 1),
        "high": round(safe_high, 1),
    }


def classify_risk(empty_ratio: float | int, mid_threshold: float, high_threshold: float) -> dict[str, str]:
    """按阈值将单条记录分为低/中/高风险。"""
    numeric = float(empty_ratio or 0.0)
    mid = float(mid_threshold) / 100.0
    high = float(high_threshold) / 100.0
    if numeric >= high:
        return {"label": "高风险", "class_name": "high"}
    if numeric >= mid:
        return {"label": "中风险", "class_name": "mid"}
    return {"label": "低风险", "class_name": "low"}


def attach_risk(record: dict, thresholds: dict[str, float]) -> dict:
    """为记录补充风险标签，避免前端重复推导。"""
    tagged = dict(record)
    risk = classify_risk(tagged.get("empty_ratio", 0.0), thresholds["mid"], thresholds["high"])
    tagged["risk_label"] = risk["label"]
    tagged["risk_class"] = risk["class_name"]
    return tagged


def build_summary(records: list[dict], model_family: str, version: str) -> dict:
    """构建批次总览统计。"""
    if not records:
        return {
            "version": f"{model_family}-{version}",
            "image_count": 0,
            "total_product": 0,
            "total_empty": 0,
            "empty_ratio": 0.0,
            "worst_image": "",
            "max_rows_detected": 0,
            "avg_rows": 0.0,
            "avg_product_per_image": 0.0,
            "avg_empty_per_image": 0.0,
        }

    total_product = sum(int(record.get("product_count", 0)) for record in records)
    total_empty = sum(int(record.get("empty_count", 0)) for record in records)
    total_target = total_product + total_empty
    max_rows = max(int(record.get("actual_rows", record.get("n_rows", 0))) for record in records)
    worst_image = max(records, key=lambda item: float(item.get("empty_ratio", 0))).get("file", "")

    return {
        "version": f"{model_family}-{version}",
        "image_count": len(records),
        "total_product": total_product,
        "total_empty": total_empty,
        "empty_ratio": round(total_empty / total_target, 4) if total_target else 0.0,
        "worst_image": worst_image,
        "max_rows_detected": max_rows,
        "avg_rows": round(sum(int(record.get("actual_rows", record.get("n_rows", 0))) for record in records) / len(records), 2),
        "avg_product_per_image": round(total_product / len(records), 2),
        "avg_empty_per_image": round(total_empty / len(records), 2),
    }


def _risk_matches(record: dict, risk_filter: str) -> bool:
    if risk_filter == "all":
        return True
    if risk_filter == "high":
        return record.get("risk_class") == "high"
    if risk_filter == "mid":
        return record.get("risk_class") == "mid"
    if risk_filter in {"ok", "low"}:
        return record.get("risk_class") == "low"
    return True


def query_records(
    records: list[dict],
    *,
    keyword: str = "",
    risk_filter: str = "all",
    sort_key: str = "default",
    sort_dir: str = "desc",
    mid_threshold: float = DEFAULT_MID_THRESHOLD,
    high_threshold: float = DEFAULT_HIGH_THRESHOLD,
) -> list[dict]:
    """对记录应用风险标记、搜索、筛选和排序。"""
    thresholds = normalize_thresholds(mid_threshold, high_threshold)
    keyword_value = str(keyword or "").strip().lower()

    filtered: list[dict] = []
    for record in records:
        # 风险标签在服务端统一计算，前端只消费结果。
        tagged = attach_risk(record, thresholds)
        file_name = str(tagged.get("file", "")).lower()
        if keyword_value and keyword_value not in file_name:
            continue
        if not _risk_matches(tagged, risk_filter):
            continue
        filtered.append(tagged)

    reverse = str(sort_dir or "desc").lower() != "asc"
    normalized_sort = sort_key or "default"
    if normalized_sort == "default":
        filtered.sort(key=lambda item: str(item.get("file", "")), reverse=reverse)
        return filtered

    def _safe_sort_value(item):
        try:
            return float(item.get(normalized_sort, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    filtered.sort(key=_safe_sort_value, reverse=reverse)
    return filtered


def paginate_records(records: list[dict], page: int, per_page: int) -> dict:
    """将记录集切分为分页响应。"""
    safe_per_page = max(1, min(int(per_page or DEFAULT_PER_PAGE), MAX_PER_PAGE))
    total = len(records)
    total_pages = max(1, math.ceil(total / safe_per_page)) if total else 1
    # 请求页码越界时收敛到有效范围，避免返回空页导致前端状态错乱。
    safe_page = max(1, min(int(page or 1), total_pages))
    start = (safe_page - 1) * safe_per_page
    end = start + safe_per_page
    return {
        "items": records[start:end],
        "page": safe_page,
        "per_page": safe_per_page,
        "total": total,
        "total_pages": total_pages,
    }


def build_dashboard_page(
    records: list[dict],
    model_family: str,
    version: str,
    *,
    keyword: str = "",
    risk_filter: str = "all",
    mid_threshold: float = DEFAULT_MID_THRESHOLD,
    high_threshold: float = DEFAULT_HIGH_THRESHOLD,
    limit: int | None = None,
) -> dict:
    """构建总览页数据。"""
    thresholds = normalize_thresholds(mid_threshold, high_threshold)
    queried = query_records(
        records,
        keyword=keyword,
        risk_filter=risk_filter,
        sort_key="empty_ratio",
        sort_dir="desc",
        mid_threshold=thresholds["mid"],
        high_threshold=thresholds["high"],
    )
    safe_limit = max(1, int(limit)) if limit not in (None, 0) else None
    displayed_records = queried[:safe_limit] if safe_limit is not None else queried
    all_tagged = query_records(records, mid_threshold=thresholds["mid"], high_threshold=thresholds["high"])
    high_risk_count = sum(1 for record in all_tagged if record["risk_class"] == "high")
    return {
        "summary": build_summary(records, model_family, version),
        "records": displayed_records,
        "record_total": len(records),
        "filtered_total": len(queried),
        "displayed_total": len(displayed_records),
        "display_limit": safe_limit,
        "is_truncated": len(displayed_records) < len(queried),
        "high_risk_count": high_risk_count,
        "thresholds": thresholds,
    }


def build_records_page(
    records: list[dict],
    model_family: str,
    version: str,
    *,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
    keyword: str = "",
    risk_filter: str = "all",
    sort_key: str = "default",
    sort_dir: str = "desc",
    mid_threshold: float = DEFAULT_MID_THRESHOLD,
    high_threshold: float = DEFAULT_HIGH_THRESHOLD,
) -> dict:
    """构建检测记录页数据。"""
    thresholds = normalize_thresholds(mid_threshold, high_threshold)
    queried = query_records(
        records,
        keyword=keyword,
        risk_filter=risk_filter,
        sort_key=sort_key,
        sort_dir=sort_dir,
        mid_threshold=thresholds["mid"],
        high_threshold=thresholds["high"],
    )
    pagination = paginate_records(queried, page, per_page)
    current_total = len(queried)
    avg_empty_ratio = (
        round(sum(float(record.get("empty_ratio", 0) or 0) for record in queried) / current_total, 4)
        if current_total
        else 0.0
    )
    max_rows = max((int(record.get("actual_rows", record.get("n_rows", 0))) for record in queried), default=0)
    high_risk_count = sum(1 for record in queried if record.get("risk_class") == "high")

    return {
        "summary": build_summary(records, model_family, version),
        "records": pagination["items"],
        "page": pagination["page"],
        "per_page": pagination["per_page"],
        "total": pagination["total"],
        "total_pages": pagination["total_pages"],
        "thresholds": thresholds,
        "filters": {
            "keyword": keyword,
            "risk_filter": risk_filter,
            "sort_key": sort_key,
            "sort_dir": sort_dir,
        },
        "stats": {
            "current_count": current_total,
            "high_risk_count": high_risk_count,
            "avg_empty_ratio": avg_empty_ratio,
            "max_rows": max_rows,
        },
    }
