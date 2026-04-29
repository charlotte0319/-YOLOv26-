"""
web_dashboard/services/system_service.py

作用：
- 汇总系统状态页需要的路径可用性、运行快照与基础检查结果。

调用来源：
- `web_dashboard/__init__.py` 中的 `/api/system` 路由调用 `build_system_page()`。
- `web_dashboard/data_service.py` 作为兼容门面转发导出。

调用方式：
- `build_system_status(snapshot, csv_path, image_dir, train_dir)`
- `build_system_page(summary, snapshot, csv_path, image_dir, train_dir)`
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from inference_pipeline.run_artifacts import BEIJING_TZ, now_beijing_str
from project_config import CSV_PATH, NN_IMG_DIR, TRAIN_OUT_DIR


def _latest_file_timestamp(target_dir: Path) -> str:
    """返回目录中文件的最近更新时间。"""
    files = [path for path in target_dir.glob("*") if path.is_file()]
    if not files:
        return ""
    latest = max(files, key=lambda path: path.stat().st_mtime)
    return datetime.fromtimestamp(latest.stat().st_mtime, tz=BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")


def build_system_status(
    snapshot: dict,
    csv_path: Path,
    image_dir: Path,
    train_dir: Path = TRAIN_OUT_DIR,
) -> dict:
    """构建系统状态页需要的信息。"""
    csv_exists = csv_path.exists()
    image_dir_exists = image_dir.exists()
    train_dir_exists = train_dir.exists()

    image_count = len([path for path in image_dir.glob("*") if path.is_file()]) if image_dir_exists else 0
    train_asset_count = len([path for path in train_dir.glob("*") if path.is_file()]) if train_dir_exists else 0
    csv_updated_at = (
        datetime.fromtimestamp(csv_path.stat().st_mtime, tz=BEIJING_TZ).strftime("%Y-%m-%d %H:%M:%S")
        if csv_exists
        else ""
    )

    return {
        "service": "dashboard",
        "checked_at": now_beijing_str(),
        "csv_exists": csv_exists,
        "image_dir_exists": image_dir_exists,
        "train_dir_exists": train_dir_exists,
        "predict_image_count": image_count,
        "train_asset_count": train_asset_count,
        "csv_updated_at": csv_updated_at,
        "train_updated_at": _latest_file_timestamp(train_dir) if train_dir_exists else "",
        "snapshot": snapshot,
    }


def build_system_page(
    summary: dict,
    snapshot: dict,
    csv_path: Path = CSV_PATH,
    image_dir: Path = NN_IMG_DIR,
    train_dir: Path = TRAIN_OUT_DIR,
) -> dict:
    """组合系统状态页面响应数据。"""
    return {
        "summary": summary,
        "snapshot": snapshot,
        "system": build_system_status(snapshot, csv_path, image_dir, train_dir),
    }
