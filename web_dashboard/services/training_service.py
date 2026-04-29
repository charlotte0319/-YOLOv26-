"""
web_dashboard/services/training_service.py

作用：
- 读取训练结果 CSV、发现训练图像，并生成训练页需要的结构化数据。

调用来源：
- `web_dashboard/__init__.py` 中的 `/api/training` 路由调用 `build_training_page()`。
- `web_dashboard/data_service.py` 作为兼容门面转发导出。

调用方式：
- `parse_training_results_csv()`
- `discover_training_assets()`
- `build_training_page(summary, snapshot)`
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from project_config import TRAIN_OUT_DIR

TRAIN_RESULTS_CSV = TRAIN_OUT_DIR / "results.csv"

CORE_ASSETS = ["results.png"]
METRIC_ASSETS = [
    "confusion_matrix.png",
    "confusion_matrix_normalized.png",
    "BoxPR_curve.png",
    "BoxP_curve.png",
    "BoxR_curve.png",
    "BoxF1_curve.png",
    "labels.jpg",
]


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


def parse_training_results_csv(results_csv: Path = TRAIN_RESULTS_CSV) -> dict:
    """解析 YOLO 训练 results.csv，并提炼常用指标。"""
    default_payload = {
        "exists": False,
        "latest_epoch": 0,
        "best_epoch": 0,
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "map50": 0.0,
        "map50_95": 0.0,
        "best_map50_95": 0.0,
        "train_box_loss": 0.0,
        "train_cls_loss": 0.0,
        "train_dfl_loss": 0.0,
        "val_box_loss": 0.0,
        "val_cls_loss": 0.0,
        "val_dfl_loss": 0.0,
        "train_time": 0.0,
    }
    if not results_csv.exists():
        return default_payload

    with results_csv.open(encoding="utf-8-sig") as file:
        rows = list(csv.DictReader(file))

    if not rows:
        return {**default_payload, "exists": True}

    latest = rows[-1]
    best = max(rows, key=lambda row: _safe_float(row.get("metrics/mAP50-95(B)", 0), 0.0))
    precision = _safe_float(latest.get("metrics/precision(B)", 0), 0.0)
    recall = _safe_float(latest.get("metrics/recall(B)", 0), 0.0)
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    return {
        "exists": True,
        "latest_epoch": _safe_int(latest.get("epoch", 0), 0),
        "best_epoch": _safe_int(best.get("epoch", 0), 0),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "map50": round(_safe_float(latest.get("metrics/mAP50(B)", 0), 0.0), 4),
        "map50_95": round(_safe_float(latest.get("metrics/mAP50-95(B)", 0), 0.0), 4),
        "best_map50_95": round(_safe_float(best.get("metrics/mAP50-95(B)", 0), 0.0), 4),
        "train_box_loss": round(_safe_float(latest.get("train/box_loss", 0), 0.0), 4),
        "train_cls_loss": round(_safe_float(latest.get("train/cls_loss", 0), 0.0), 4),
        "train_dfl_loss": round(_safe_float(latest.get("train/dfl_loss", 0), 0.0), 4),
        "val_box_loss": round(_safe_float(latest.get("val/box_loss", 0), 0.0), 4),
        "val_cls_loss": round(_safe_float(latest.get("val/cls_loss", 0), 0.0), 4),
        "val_dfl_loss": round(_safe_float(latest.get("val/dfl_loss", 0), 0.0), 4),
        "train_time": round(_safe_float(latest.get("time", 0), 0.0), 2),
    }


def discover_training_assets(train_dir: Path = TRAIN_OUT_DIR) -> dict:
    """收集训练结果图像，并按前端页面需要分组。"""
    core_assets = [name for name in CORE_ASSETS if (train_dir / name).exists()]
    metric_assets = [name for name in METRIC_ASSETS if (train_dir / name).exists()]
    validation_samples = sorted(file.name for file in train_dir.glob("val_batch*.jpg"))
    training_samples = sorted(file.name for file in train_dir.glob("train_batch*.jpg"))

    return {
        "train_dir": str(train_dir),
        "exists": train_dir.exists(),
        "core_assets": core_assets,
        "metric_assets": metric_assets,
        "validation_samples": validation_samples,
        "training_samples": training_samples,
        "primary_assets": core_assets,
        "curve_assets": metric_assets,
    }


def safe_resolve_asset(base_dir: Path, name: str) -> Path | None:
    """安全解析训练产物路径，防止路径穿越。"""
    candidate = (base_dir / name).resolve()
    try:
        candidate.relative_to(base_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.exists() else None


def build_model_report(summary: dict, training_metrics: dict, training_assets: dict | None = None) -> dict:
    """构建训练页需要的运行概览信息。"""
    highlights = [
        f"当前活动模型版本为 {summary.get('version', '-')}，共统计 {summary.get('image_count', 0)} 张预测图像。",
        f"最新主指标 mAP50-95 为 {training_metrics.get('map50_95', 0):.4f}，Precision 为 {training_metrics.get('precision', 0):.4f}，Recall 为 {training_metrics.get('recall', 0):.4f}。",
        f"最佳 Epoch 为 {training_metrics.get('best_epoch', 0)}，建议优先结合 results.png 与混淆矩阵检查收敛和误检情况。",
        f"当前批次平均每张图像检测到 {summary.get('avg_product_per_image', 0)} 个商品、{summary.get('avg_empty_per_image', 0)} 个空缺，平均货架层数为 {summary.get('avg_rows', 0)}。",
    ]
    training_assets = training_assets or {}
    return {
        "highlights": highlights,
        "primary_assets": training_assets.get("primary_assets", []),
        "curve_assets": training_assets.get("curve_assets", []),
    }


def build_training_page(summary: dict, snapshot: dict) -> dict:
    """组合训练页面响应数据。"""
    metrics = parse_training_results_csv()
    assets = discover_training_assets()
    return {
        "summary": summary,
        "snapshot": snapshot,
        "training_metrics": metrics,
        "training_assets": assets,
        "training_report": build_model_report(summary, metrics, assets),
    }
