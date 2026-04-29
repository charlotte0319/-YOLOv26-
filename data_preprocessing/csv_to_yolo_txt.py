"""
data_preprocessing/csv_to_yolo_txt.py

作用：
- 将 SKU110K 的 CSV 标注转换为 YOLO TXT 标注格式。

实现方式：
- 读取 annotations_{split}.csv。
- 将 xyxy 像素坐标归一化为 YOLO 的 cx cy bw bh。
- 按图片名聚合并并行写入 labels/{split}/*.txt。

关键函数：
- write_label_file(args)
- process_split(csv_file, split)
- main()

调用方式：
- python data_preprocessing/csv_to_yolo_txt.py
"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import polars as pl
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ROOT_DIR = PROJECT_ROOT / "data" / "SKU110K_fixed"
COLUMNS = ["image", "x1", "y1", "x2", "y2", "class", "image_width", "image_height"]


def write_label_file(args) -> None:
    """写入单个 YOLO txt 标注文件。"""
    label_dir, stem, content = args
    (label_dir / f"{stem}.txt").write_text(content + "\n", encoding="utf-8")


def process_split(csv_file: str, split: str) -> None:
    """处理单个 split（train/val/test）。"""
    csv_path = ROOT_DIR / "annotations" / csv_file
    if not csv_path.exists():
        print(f"[预处理] 缺少文件，已跳过：{csv_file}")
        return

    print(f"[预处理] 开始处理 {split} 标注：{csv_path}")
    df = pl.read_csv(csv_path, has_header=False, new_columns=COLUMNS).with_columns(pl.col("image").str.strip_chars())
    print(f"[预处理] {split}：共 {len(df)} 条标注，{df['image'].n_unique()} 张图片。")

    df = df.with_columns(
        [
            pl.col("image").str.replace(r"\.[^.]+$", "").alias("stem"),
            ((pl.col("x1") / pl.col("image_width") + pl.col("x2") / pl.col("image_width")) / 2).alias("cx"),
            ((pl.col("y1") / pl.col("image_height") + pl.col("y2") / pl.col("image_height")) / 2).alias("cy"),
            ((pl.col("x2") - pl.col("x1")) / pl.col("image_width")).alias("bw"),
            ((pl.col("y2") - pl.col("y1")) / pl.col("image_height")).alias("bh"),
        ]
    ).with_columns(
        pl.format(
            "0 {} {} {} {}",
            pl.col("cx").round(6),
            pl.col("cy").round(6),
            pl.col("bw").round(6),
            pl.col("bh").round(6),
        ).alias("line")
    )

    grouped = df.group_by("stem").agg(pl.col("line").str.join("\n").alias("content")).to_dicts()

    label_dir = ROOT_DIR / "labels" / split
    label_dir.mkdir(parents=True, exist_ok=True)
    tasks = [(label_dir, row["stem"], row["content"]) for row in grouped]

    print(f"[预处理] {split}：准备写入 {len(tasks)} 个标签文件。")
    with ThreadPoolExecutor(max_workers=16) as executor:
        list(tqdm(executor.map(write_label_file, tasks), total=len(tasks), desc=f"{split} 转换", unit="文件"))

    print(f"[预处理] {split} 转换完成。")


def main() -> None:
    """脚本入口。"""
    print("[预处理] CSV 转 YOLO TXT 开始。")
    for split in ("train", "val", "test"):
        (ROOT_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)

    process_split("annotations_train.csv", "train")
    process_split("annotations_val.csv", "val")
    process_split("annotations_test.csv", "test")

    print("[预处理] 全部标签转换完成。")


if __name__ == "__main__":
    main()
