"""
model_fusion/h5_to_pt_converter.py

作用：
- 将 h5 格式权重提取并转换为 PyTorch 可读的 .pt 字典文件。

实现方式：
- 仅保留 backbone 相关层（conv/bn/res*），过滤检测头。
- 对 Conv/Dense 权重做维度重排以匹配 PyTorch 格式。

关键函数：
- convert_kernel(weight)
- should_skip_layer(name)
- should_keep_layer(name)
- convert_h5_to_pt(h5_path, output_pt)

调用方式：
- python model_fusion/h5_to_pt_converter.py
"""

import h5py
import numpy as np
import torch

H5_PATH = "model/iou_resnet50_csv_06.h5"
OUTPUT_PT = "model/sku110k_resnet50_backbone.pt"

SKIP_KEYWORDS = ["retinanet", "regression", "classification", "pyramid", "fpn_", "predict", "output"]
KEEP_KEYWORDS = ["conv", "bn", "batch_norm", "resnet50", "res2", "res3", "res4", "res5"]


def convert_kernel(weight_array: np.ndarray) -> torch.FloatTensor:
    """将 Keras 权重格式转换为 PyTorch 格式。"""
    if len(weight_array.shape) == 4:
        return torch.FloatTensor(np.transpose(weight_array, (3, 2, 0, 1)))
    if len(weight_array.shape) == 2:
        return torch.FloatTensor(np.transpose(weight_array, (1, 0)))
    return torch.FloatTensor(weight_array)


def should_skip_layer(name: str) -> bool:
    """判断是否属于应跳过的检测头相关层。"""
    lower_name = name.lower()
    return any(keyword in lower_name for keyword in SKIP_KEYWORDS)


def should_keep_layer(name: str) -> bool:
    """判断是否属于应保留的 backbone 相关层。"""
    lower_name = name.lower()
    return any(keyword in lower_name for keyword in KEEP_KEYWORDS)


def convert_h5_to_pt(h5_path: str, output_pt: str) -> int:
    """执行转换并返回成功提取的层数。"""
    print(f"[融合] 开始读取 H5 权重：{h5_path}")
    converted: dict[str, torch.FloatTensor] = {}
    layer_count = 0

    with h5py.File(h5_path, "r") as file:
        print("[融合] H5 顶层键：")
        print(list(file.keys()))

        def extract_weights(name, obj):
            nonlocal layer_count
            if not isinstance(obj, h5py.Dataset):
                return
            if should_skip_layer(name) or not should_keep_layer(name):
                return

            weight = np.array(obj)
            if weight.size == 0:
                return

            key = name.replace("/", ".")
            converted[key] = convert_kernel(weight)
            layer_count += 1

            if layer_count <= 10 or layer_count % 20 == 0:
                print(f"[融合] 已提取 {layer_count} 层：{name} {weight.shape}")

        file.visititems(extract_weights)

    print(f"[融合] 权重提取结束，共 {layer_count} 层。")

    if layer_count == 0:
        print("[融合] 未提取到有效层，输出完整结构供排查：")
        with h5py.File(h5_path, "r") as file:
            def print_all(name, obj):
                if isinstance(obj, h5py.Dataset):
                    print(f"  {name}: {obj.shape}")

            file.visititems(print_all)
        return 0

    torch.save(converted, output_pt)
    print(f"[融合] 转换完成，已保存：{output_pt}")
    return layer_count


def main() -> None:
    """脚本入口。"""
    convert_h5_to_pt(H5_PATH, OUTPUT_PT)


if __name__ == "__main__":
    main()
