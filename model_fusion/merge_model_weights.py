"""
model_fusion/merge_model_weights.py

作用：
- 将 YOLO 训练权重与 SKU backbone 权重按比例融合，生成新的 warm-start 权重。

实现方式：
- 逐层匹配形状，一旦匹配则按 ALPHA 混合。
- 无匹配层保持原 YOLO 权重不变。

关键函数：
- blend_state_dict(v2_state, sku_weights, alpha)
- main()

调用方式：
- python model_fusion/merge_model_weights.py
"""

from pathlib import Path

import torch

V2_BEST = "runs_yolo26n/train_weights/train_v2/weights/best.pt"
SKU_PT = "model/sku110k_resnet50_backbone.pt"
V3_OUT = "runs_yolo26n/train_weights/train_v3/weights/best.pt"
ALPHA = 0.7  # v2 占比，SKU 占比为 (1 - ALPHA)


def blend_state_dict(v2_state: dict, sku_weights: dict, alpha: float):
    """按形状匹配融合权重，返回 (new_state, matched, kept)。"""
    new_state = {}
    matched = 0
    kept = 0

    sku_values = list(sku_weights.values())
    for key, v2_tensor in v2_state.items():
        for sku_tensor in sku_values:
            if sku_tensor.shape == v2_tensor.shape:
                new_state[key] = alpha * v2_tensor + (1 - alpha) * sku_tensor
                matched += 1
                break
        else:
            new_state[key] = v2_tensor
            kept += 1

    return new_state, matched, kept


def main() -> None:
    """脚本入口。"""
    Path(V3_OUT).parent.mkdir(parents=True, exist_ok=True)

    print(f"[融合] 正在加载 YOLO 检查点：{V2_BEST}")
    v2_ckpt = torch.load(V2_BEST, map_location="cpu", weights_only=False)
    v2_model = v2_ckpt["model"]
    v2_state = v2_model.state_dict()

    print(f"[融合] 正在加载 SKU 骨干权重：{SKU_PT}")
    sku_weights = torch.load(SKU_PT, map_location="cpu")

    print("[融合] 开始按形状匹配并融合参数。")
    new_state, matched, kept = blend_state_dict(v2_state, sku_weights, ALPHA)
    print(f"[融合] 融合层数：{matched}")
    print(f"[融合] 保留原层数：{kept}")

    v2_model.load_state_dict(new_state, strict=True)
    v2_ckpt["model"] = v2_model
    v2_ckpt.pop("optimizer", None)
    v2_ckpt.pop("best_fitness", None)
    v2_ckpt.pop("ema", None)
    v2_ckpt["epoch"] = -1

    torch.save(v2_ckpt, V3_OUT)
    print(f"[融合] 融合权重已保存：{V3_OUT}")
    print("[融合] 下一步：修改 project_config.py 的 TRAIN_PREDICT_VERSION 后运行 train.py")


if __name__ == "__main__":
    main()
