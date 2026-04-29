"""
evaluation/evaluate_predictions.py

作用：
- 对预测 CSV 与人工标注 CSV 做离线对比评估。
- 输出适合论文与答辩引用的 JSON / Markdown 报告。

要求：
- 两份 CSV 至少都包含 `file` 列。
- 标注 CSV 推荐包含：`n_rows`、`empty_count`、`product_count`、`empty_ratio`。

调用方式：
- python evaluation/evaluate_predictions.py --pred runs_yolo26n/analysis/csv_v1/analysis_results.csv --gt path/to/ground_truth.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean

from inference_pipeline.time_utils import now_beijing_str


def read_csv_records(path: Path) -> list[dict]:
    """读取 CSV 记录。"""
    with open(path, encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def to_float(value, default: float = 0.0) -> float:
    """安全转换为 float。"""
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value, default: int = 0) -> int:
    """安全转换为 int。"""
    if value in (None, ""):
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def build_index(records: list[dict]) -> dict[str, dict]:
    """按 file 字段构建索引。"""
    return {str(record["file"]): record for record in records if record.get("file")}


def compute_metrics(pred_records: list[dict], gt_records: list[dict]) -> dict:
    """计算行数与目标数量相关指标。"""
    pred_index = build_index(pred_records)
    gt_index = build_index(gt_records)

    shared_files = sorted(set(pred_index) & set(gt_index))
    if not shared_files:
        raise ValueError("预测 CSV 与标注 CSV 没有共同 file 字段，无法评估。")

    row_matches = []
    row_abs_errors = []
    empty_abs_errors = []
    product_abs_errors = []
    ratio_abs_errors = []

    per_file = []
    for file_name in shared_files:
        pred = pred_index[file_name]
        gt = gt_index[file_name]

        pred_rows = to_int(pred.get("n_rows"))
        gt_rows = to_int(gt.get("n_rows"))
        pred_empty = to_int(pred.get("empty_count"))
        gt_empty = to_int(gt.get("empty_count"))
        pred_product = to_int(pred.get("product_count"))
        gt_product = to_int(gt.get("product_count"))
        pred_ratio = to_float(pred.get("empty_ratio"))
        gt_ratio = to_float(gt.get("empty_ratio"))

        row_match = int(pred_rows == gt_rows)
        row_error = abs(pred_rows - gt_rows)
        empty_error = abs(pred_empty - gt_empty)
        product_error = abs(pred_product - gt_product)
        ratio_error = abs(pred_ratio - gt_ratio)

        row_matches.append(row_match)
        row_abs_errors.append(row_error)
        empty_abs_errors.append(empty_error)
        product_abs_errors.append(product_error)
        ratio_abs_errors.append(ratio_error)

        per_file.append(
            {
                "file": file_name,
                "pred_n_rows": pred_rows,
                "gt_n_rows": gt_rows,
                "row_abs_error": row_error,
                "pred_empty_count": pred_empty,
                "gt_empty_count": gt_empty,
                "empty_abs_error": empty_error,
            }
        )

    return {
        "matched_file_count": len(shared_files),
        "row_accuracy": round(mean(row_matches), 4),
        "row_mae": round(mean(row_abs_errors), 4),
        "empty_count_mae": round(mean(empty_abs_errors), 4),
        "product_count_mae": round(mean(product_abs_errors), 4),
        "empty_ratio_mae": round(mean(ratio_abs_errors), 6),
        "per_file": per_file,
    }


def write_json_report(path: Path, payload: dict) -> None:
    """写入 JSON 报告。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def write_markdown_report(path: Path, payload: dict) -> None:
    """写入 Markdown 报告。"""
    lines = [
        "# 预测评估报告",
        "",
        f"- 生成时间：{payload['generated_at']}",
        f"- 预测文件：`{payload['pred_csv']}`",
        f"- 标注文件：`{payload['gt_csv']}`",
        f"- 匹配样本数：`{payload['metrics']['matched_file_count']}`",
        f"- 行数准确率：`{payload['metrics']['row_accuracy']}`",
        f"- 行数 MAE：`{payload['metrics']['row_mae']}`",
        f"- 空缺数 MAE：`{payload['metrics']['empty_count_mae']}`",
        f"- 商品数 MAE：`{payload['metrics']['product_count_mae']}`",
        f"- 空缺率 MAE：`{payload['metrics']['empty_ratio_mae']}`",
        "",
        "## 误差样本（前 20 条）",
        "",
        "| file | pred_n_rows | gt_n_rows | row_abs_error | pred_empty_count | gt_empty_count | empty_abs_error |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    top_items = sorted(
        payload["metrics"]["per_file"],
        key=lambda item: (item["row_abs_error"], item["empty_abs_error"]),
        reverse=True,
    )[:20]
    for item in top_items:
        lines.append(
            f"| {item['file']} | {item['pred_n_rows']} | {item['gt_n_rows']} | "
            f"{item['row_abs_error']} | {item['pred_empty_count']} | {item['gt_empty_count']} | "
            f"{item['empty_abs_error']} |"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        file.write("\n".join(lines) + "\n")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="评估预测 CSV 与人工标注 CSV 的一致性。")
    parser.add_argument("--pred", required=True, help="预测 CSV 路径")
    parser.add_argument("--gt", required=True, help="人工标注 CSV 路径")
    parser.add_argument(
        "--out-dir",
        default="evaluation_reports",
        help="评估报告输出目录，默认 evaluation_reports",
    )
    return parser.parse_args()


def main() -> None:
    """脚本入口。"""
    args = parse_args()
    pred_path = Path(args.pred)
    gt_path = Path(args.gt)
    out_dir = Path(args.out_dir)

    print(f"[评估] 读取预测文件：{pred_path}")
    print(f"[评估] 读取标注文件：{gt_path}")

    pred_records = read_csv_records(pred_path)
    gt_records = read_csv_records(gt_path)
    metrics = compute_metrics(pred_records, gt_records)

    generated_at = now_beijing_str()
    payload = {
        "generated_at": generated_at,
        "pred_csv": str(pred_path),
        "gt_csv": str(gt_path),
        "metrics": metrics,
    }

    json_path = out_dir / "evaluation_report.json"
    md_path = out_dir / "evaluation_report.md"
    write_json_report(json_path, payload)
    write_markdown_report(md_path, payload)

    print("[评估] 评估完成。")
    print(f"[评估] 行数准确率：{metrics['row_accuracy']}")
    print(f"[评估] 行数 MAE：{metrics['row_mae']}")
    print(f"[评估] Markdown 报告：{md_path}")
    print(f"[评估] JSON 报告：{json_path}")


if __name__ == "__main__":
    main()
