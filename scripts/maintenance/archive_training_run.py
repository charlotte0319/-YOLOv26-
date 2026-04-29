"""
scripts/maintenance/archive_training_run.py

作用：
- 将指定训练输出目录压缩为 zip 归档文件，便于备份、传输和提交。

调用方式：
- `python scripts/maintenance/archive_training_run.py`
- `python scripts/maintenance/archive_training_run.py --source-dir runs_yolo26n/train_weights/train_v1`

调用来源：
- 手动归档某次训练产物。
- 被外部自动化流程或 CI 调用时也可复用。
"""

import argparse
import shutil
from pathlib import Path

from project_config import TRAIN_OUT_DIR

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ZIP_OUTPUT_DIR = ROOT / "artifacts" / "zip"


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="压缩指定训练输出目录。")
    parser.add_argument(
        "--source-dir",
        default=str(TRAIN_OUT_DIR),
        help="待压缩训练目录，默认使用当前配置对应的 TRAIN_OUT_DIR",
    )
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_ZIP_OUTPUT_DIR),
        help="zip 输出目录，默认是 artifacts/zip",
    )
    return parser.parse_args()


def main() -> None:
    """脚本入口：校验目录并执行压缩。"""
    args = parse_args()
    source_folder = Path(args.source_dir)
    zip_output_dir = Path(args.out_dir)
    output_path = zip_output_dir / source_folder.name

    if not source_folder.exists():
        print(f"[压缩] 源目录不存在：{source_folder}")
        raise SystemExit(1)

    zip_output_dir.mkdir(parents=True, exist_ok=True)
    print(f"[压缩] 开始压缩目录：{source_folder}")

    try:
        shutil.make_archive(base_name=str(output_path), format="zip", root_dir=source_folder)
        zip_file = Path(str(output_path) + ".zip")
        print(f"[压缩] 压缩完成：{zip_file}")
        print(f"[压缩] 文件大小：{zip_file.stat().st_size / 1024 / 1024:.2f} MB")
    except Exception as exc:
        print(f"[压缩] 压缩失败：{exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
