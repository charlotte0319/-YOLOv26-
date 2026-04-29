"""
inference_pipeline/csv_exporter.py

作用：
- 将分析结果 records 导出为统一 CSV 文件，供 dashboard 与后续流程读取。

实现方式：
- 动态收集所有字段，固定基础字段顺序，其他字段按字母序追加。
- 每次导出使用同一个 timestamp，表示本次推理批次时间。

关键函数：
- export_csv(records)

调用方式：
- from inference_pipeline.csv_exporter import export_csv
"""

import csv
import logging
from pathlib import Path

from project_config import CSV_PATH
from inference_pipeline.run_artifacts import now_beijing_str

logger = logging.getLogger(__name__)


class CsvExportError(RuntimeError):
    """表示分析 CSV 导出失败。"""


def export_csv(records: list[dict], csv_path: Path | str | None = None) -> None:
    """导出 records 到目标 CSV；未指定时写入默认 CSV_PATH。"""
    if not records:
        logger.info("无可导出数据，已跳过。")
        return

    target_csv = Path(csv_path) if csv_path is not None else Path(CSV_PATH)
    all_fields = set().union(*(record.keys() for record in records))

    base_fields = [
        "timestamp",
        "file",
        "product_count",
        "empty_count",
        "total",
        "empty_ratio",
        "n_rows",
        "max_rows_detected",
        "row_capacity",
    ]
    other_fields = sorted(field for field in all_fields if field not in base_fields)
    fieldnames = base_fields + other_fields

    batch_timestamp = now_beijing_str()

    try:
        target_csv.parent.mkdir(parents=True, exist_ok=True)
        logger.info("开始写入文件：%s", target_csv)
        with open(target_csv, "w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()

            for index, record in enumerate(records, start=1):
                row_data = {"timestamp": batch_timestamp}
                for field in fieldnames:
                    if field != "timestamp":
                        row_data[field] = record.get(field, "")
                writer.writerow(row_data)

                if index == 1 or index % 200 == 0 or index == len(records):
                    logger.info("已写入 %d/%d 行。", index, len(records))

        logger.info("CSV 导出完成，共 %d 行。", len(records))
    except Exception as exc:
        logger.exception("CSV 导出失败：%s", exc)
        raise CsvExportError(f"分析 CSV 导出失败：{target_csv}") from exc
