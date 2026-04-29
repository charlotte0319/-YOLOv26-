"""
inference_pipeline/run_artifacts.py

作用：
- 保存训练、推理、评估过程中的运行快照与阶段元数据。
- 为论文复现实验、工程追踪和答辩材料提供可落地的过程记录。

实现方式：
- 统一生成包含时间戳、运行快照和扩展字段的 JSON 文件。
- 每个阶段单独落盘，便于回溯训练参数、推理输入和产物目录。

关键函数：
- build_stage_snapshot(stage, extra=None)
- save_stage_snapshot(path, stage, extra=None)

调用方式：
- from inference_pipeline.run_artifacts import save_stage_snapshot
"""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")
BEIJING_TZ_NAME = "Asia/Shanghai"


def now_beijing() -> datetime:
    """返回当前北京时间。"""
    return datetime.now(BEIJING_TZ)


def now_beijing_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """返回格式化后的北京时间字符串。"""
    return now_beijing().strftime(fmt)


def now_str() -> str:
    """返回格式化后的北京时间字符串。"""
    return now_beijing_str()


def ensure_parent(path: Path) -> None:
    """确保目标文件的父目录存在。"""
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: dict) -> None:
    """将字典写入 JSON 文件。"""
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def build_stage_snapshot(stage: str, extra: dict | None = None) -> dict:
    """构建阶段快照内容。"""
    from project_config import runtime_snapshot

    snapshot = {
        "stage": stage,
        "created_at": now_str(),
        "runtime": runtime_snapshot(),
    }
    if extra:
        snapshot["extra"] = extra
    return snapshot


def save_stage_snapshot(path: Path, stage: str, extra: dict | None = None) -> Path:
    """保存阶段快照并返回输出路径。"""
    payload = build_stage_snapshot(stage, extra)
    write_json(path, payload)
    return path
