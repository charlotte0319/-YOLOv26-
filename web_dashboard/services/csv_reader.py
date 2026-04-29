"""
web_dashboard/services/csv_reader.py

作用：
- 读取预测分析 CSV，并补齐前端展示所需的逐行统计字段。
- 对 CSV 解析错误给出显式异常，而不是静默返回空列表。

实现方式：
- 将常用数字字段和 `row*_product/empty/ratio` 自动转换为 int/float。
- 根据 `row*_product` / `row*_empty` 推断真实货架层数。
- 对未变化的 CSV 使用轻量缓存，减少重复解析成本。

调用方式：
- `read_csv_data()` 读取当前主分析 CSV。
- `enrich_record(record)` 为单条记录补充派生字段。
"""

from __future__ import annotations

import csv
import logging
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from project_config import CSV_PATH, NN_IMG_DIR, TEST_IMAGE_DIR

logger = logging.getLogger(__name__)

INT_FIELDS = {"product_count", "empty_count", "n_rows", "max_rows_detected", "row_capacity", "total"}
FLOAT_FIELDS = {"empty_ratio"}
ROW_INT_PATTERN = re.compile(r"^row\d+_(product|empty)$")
ROW_FLOAT_PATTERN = re.compile(r"^row\d+_ratio$")
PLACEHOLDER_FILE_PATTERN = re.compile(r"^image\d+\.(jpg|jpeg|png|bmp|webp|tiff)$", re.IGNORECASE)


class DashboardDataError(RuntimeError):
    """表示看板后端在读取或解析 CSV 时发生了显式数据错误。"""


def to_int(value, default: int = 0) -> int:
    """安全转换为整数。"""
    if value in (None, ""):
        return default
    return int(float(value))


def to_float(value, default: float = 0.0) -> float:
    """安全转换为浮点数。"""
    if value in (None, ""):
        return default
    return float(value)


def normalize_field_value(key: str, value):
    """按字段名归一化 CSV 值类型。"""
    if key in INT_FIELDS or ROW_INT_PATTERN.match(key):
        return to_int(value)
    if key in FLOAT_FIELDS or ROW_FLOAT_PATTERN.match(key):
        return to_float(value)
    return value


def derive_actual_row_count(record: dict) -> int:
    """根据逐行统计字段推断实际存在内容的最高货架层数。"""
    configured_rows = max(0, to_int(record.get("n_rows"), 0))
    capacity = max(configured_rows, to_int(record.get("row_capacity"), 0))
    highest = configured_rows

    for index in range(1, capacity + 1):
        empty_count = to_int(record.get(f"row{index}_empty"), 0)
        product_count = to_int(record.get(f"row{index}_product"), 0)
        if empty_count > 0 or product_count > 0:
            highest = index
    return max(highest, configured_rows)


def build_row_entries(record: dict) -> list[dict]:
    """提取单张图像的逐行统计信息。"""
    actual_rows = derive_actual_row_count(record)
    entries: list[dict] = []
    for row_no in range(1, actual_rows + 1):
        product_count = to_int(record.get(f"row{row_no}_product"), 0)
        empty_count = to_int(record.get(f"row{row_no}_empty"), 0)
        empty_ratio = to_float(record.get(f"row{row_no}_ratio"), 0.0)
        entries.append(
            {
                "row_no": row_no,
                "product_count": product_count,
                "empty_count": empty_count,
                "empty_ratio": round(empty_ratio, 4),
            }
        )
    return entries


def enrich_record(record: dict) -> dict:
    """补充前端展示需要的派生字段。"""
    enriched = dict(record)
    enriched.setdefault("source_file", enriched.get("file", ""))
    enriched.setdefault("asset_file", enriched.get("file", ""))
    row_entries = build_row_entries(enriched)
    enriched.update(
        {
            "actual_rows": len(row_entries),
            "row_entries": row_entries,
            "active_row_count": sum(1 for row in row_entries if row["product_count"] > 0 or row["empty_count"] > 0),
        }
    )
    return enriched


def _csv_signature(target_csv: Path) -> tuple[str, int, int] | None:
    """生成缓存签名；文件不存在时返回 None。"""
    if not target_csv.exists():
        return None
    stat = target_csv.stat()
    return str(target_csv.resolve()), stat.st_mtime_ns, stat.st_size


def _sorted_source_image_names() -> list[str]:
    """返回测试集输入目录中的稳定排序文件名，用于修复占位图片名。"""
    if not TEST_IMAGE_DIR.exists():
        return []
    return sorted(path.name for path in TEST_IMAGE_DIR.iterdir() if path.is_file())


def _available_prediction_image_names() -> set[str]:
    """返回预测结果目录中当前可用的图片文件名集合。"""
    if not NN_IMG_DIR.exists():
        return set()
    return {path.name for path in NN_IMG_DIR.iterdir() if path.is_file()}


def _repair_placeholder_file_names(rows: list[dict]) -> list[dict]:
    """当 CSV 中只出现 image0.jpg 这类占位名时，按测试集顺序恢复真实文件名。"""
    if not rows:
        return rows

    csv_names = [str(row.get("file", "")).strip() for row in rows]
    if not csv_names or not all(PLACEHOLDER_FILE_PATTERN.fullmatch(name) for name in csv_names):
        for row in rows:
            original = str(row.get("file", "")).strip()
            row["source_file"] = original
            row["asset_file"] = original
        return rows

    source_names = _sorted_source_image_names()
    if len(source_names) != len(rows):
        for row in rows:
            original = str(row.get("file", "")).strip()
            row["source_file"] = original
            row["asset_file"] = original
        return rows

    available_assets = _available_prediction_image_names()
    repaired_rows: list[dict] = []
    for index, row in enumerate(rows):
        original_asset_name = csv_names[index]
        source_name = source_names[index]
        asset_name = source_name if source_name in available_assets else original_asset_name
        repaired = dict(row)
        repaired["source_file"] = source_name
        repaired["asset_file"] = asset_name
        repaired["file"] = source_name
        repaired_rows.append(repaired)
    return repaired_rows


@lru_cache(maxsize=8)
def _read_csv_cached(path_str: str, _mtime_ns: int, _size: int) -> tuple[dict, ...]:
    """按文件签名缓存解析结果，避免重复读取未变化文件。"""
    target_csv = Path(path_str)
    try:
        with target_csv.open(encoding="utf-8-sig") as file:
            reader = csv.DictReader(file)
            rows: list[dict] = []
            for row in reader:
                normalized = {key: normalize_field_value(key, value) for key, value in dict(row).items()}
                rows.append(normalized)
            repaired_rows = _repair_placeholder_file_names(rows)
            return tuple(enrich_record(row) for row in repaired_rows)
    except Exception as exc:  # pragma: no cover - 异常路径由 read_csv_data 统一暴露
        raise DashboardDataError(f"读取预测 CSV 失败：{target_csv}") from exc


def read_csv_data(csv_path: Path | None = None) -> list[dict]:
    """读取预测分析 CSV，并把常用数字字段转换为数值。"""
    target_csv = csv_path or CSV_PATH
    signature = _csv_signature(target_csv)
    if signature is None:
        return []

    try:
        return deepcopy(list(_read_csv_cached(*signature)))
    except DashboardDataError:
        logger.exception("读取预测 CSV 失败：%s", target_csv)
        raise
    except Exception as exc:  # pragma: no cover - 兜底异常包装
        logger.exception("读取预测 CSV 失败：%s", target_csv)
        raise DashboardDataError(f"读取预测 CSV 失败：{target_csv}") from exc
