"""
scripts/maintenance/rename_weight_classes.py

作用：
- 修正权重文件中的类别名称映射，并另存为新的权重文件。

调用方式：
- `python scripts/maintenance/rename_weight_classes.py`
- `python scripts/maintenance/rename_weight_classes.py --weight runs_yolo26n/train_weights/train_v1/weights/best.pt`

调用来源：
- 手动修复历史权重中的类别名。
- 模型发布前统一整理权重元信息。
"""

import argparse
from pathlib import Path

from ultralytics import YOLO

from project_config import BEST_PT


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    default_weight = BEST_PT
    default_output = default_weight.with_name(f"{default_weight.stem}_renamed.pt")

    parser = argparse.ArgumentParser(description="修正权重中的类别名称映射。")
    parser.add_argument("--weight", default=str(default_weight), help="输入权重路径，默认使用当前配置对应的 BEST_PT")
    parser.add_argument("--output", default=str(default_output), help="输出权重路径，默认在同目录生成 *_renamed.pt")
    parser.add_argument("--product-name", default="商品", help="class 0 的名称")
    parser.add_argument("--empty-name", default="空缺", help="class 1 的名称")
    return parser.parse_args()


def main() -> None:
    """脚本入口：加载权重、覆盖类别名并保存。"""
    args = parse_args()
    weight_path = Path(args.weight)
    output_path = Path(args.output)
    class_names = {0: args.product_name, 1: args.empty_name}

    if not weight_path.exists():
        print(f"[权重] 未找到权重文件：{weight_path}")
        raise SystemExit(1)

    print(f"[权重] 正在加载权重：{weight_path}")
    model = YOLO(str(weight_path))

    print("[权重] 正在写入类别名称映射。")
    model.model.names = class_names

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"[权重] 正在保存新权重：{output_path}")
    model.save(str(output_path))
    print("[权重] 权重重命名处理完成。")


if __name__ == "__main__":
    main()
