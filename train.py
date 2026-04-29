"""
train.py

作用：
- 使用 Ultralytics YOLO 按 project_config.py 的配置执行训练。

实现方式：
- 读取模型与数据配置路径。
- 统一设置多线程与 cuDNN 参数。
- 调用 model.train() 并将结果写入 runs 目录。
- 训练参数中的设备、线程数和图像尺寸由配置统一提供。

关键函数：
- configure_runtime()：设置环境变量与推理/训练后端参数。
- build_train_kwargs()：集中维护训练参数，不改变原有功能。
- main()：训练入口。

调用方式：
- python train.py
"""

import gc
import os
from pathlib import Path

from inference_pipeline.run_artifacts import save_stage_snapshot
from project_config import (
    MODEL_PATH,
    ROOT,
    RUNS_DIR,
    TRAIN_IMGSZ,
    TRAIN_PREDICT_VERSION,
    TRAIN_STATIC_KWARGS,
    get_training_yaml_path,
    init_project,
    normalize_worker_count,
    resolve_yolo_device,
)


def configure_runtime() -> None:
    """配置并行与 CUDA 后端参数。"""
    import torch

    cpu_count = os.cpu_count() or 1
    os.environ["OMP_NUM_THREADS"] = str(cpu_count)
    os.environ["MKL_NUM_THREADS"] = str(cpu_count)
    os.environ["OPENBLAS_NUM_THREADS"] = str(cpu_count)
    os.environ["YOLO_CONFIG_DIR"] = str(ROOT / "model")

    torch.backends.cudnn.benchmark = True
    torch.backends.cudnn.enabled = True


def build_train_kwargs(data_yaml_path: Path, device: str | int) -> dict:
    """返回训练参数（默认行为保持不变，但允许通过配置覆盖关键运行项）。"""
    return {
        "data": str(data_yaml_path),
        "imgsz": TRAIN_IMGSZ,
        "device": device,
        "workers": normalize_worker_count(),
        **TRAIN_STATIC_KWARGS,
        "name": f"train_{TRAIN_PREDICT_VERSION}",
        "project": str(RUNS_DIR / "train_weights"),
    }


def main() -> None:
    """训练入口函数。"""
    import torch
    from ultralytics import YOLO

    print("[训练] 正在初始化运行环境...")
    init_project(stage="train")
    configure_runtime()

    data_yaml_path = get_training_yaml_path()
    device = resolve_yolo_device(probe_runtime=True)
    workers = normalize_worker_count()
    train_kwargs = build_train_kwargs(data_yaml_path, device)

    train_output_dir = RUNS_DIR / "train_weights" / f"train_{TRAIN_PREDICT_VERSION}"
    save_stage_snapshot(
        train_output_dir / "train_runtime_snapshot.json",
        stage="train",
        extra={"train_kwargs": train_kwargs},
    )

    print(f"[训练] 准备加载训练初始化权重：{MODEL_PATH}")
    print(f"[训练] 使用设备：{device}")
    print(f"[训练] 使用线程数：{workers}")
    model = YOLO(str(MODEL_PATH))

    print("[训练] 参数准备完成，开始训练。")
    print(f"[训练] 当前版本：{TRAIN_PREDICT_VERSION}")
    print(f"[训练] 数据配置：{data_yaml_path}")
    print(f"[训练] 训练尺寸：{TRAIN_IMGSZ}")
    print(f"[训练] 输出目录：{RUNS_DIR / 'train_weights'}")
    results = model.train(**train_kwargs)

    save_stage_snapshot(
        train_output_dir / "train_completion_snapshot.json",
        stage="train_complete",
        extra={"save_dir": str(getattr(results, "save_dir", train_output_dir))},
    )

    print("[训练] 训练完成，开始释放缓存。")
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    print("[训练] 资源清理完成。")


if __name__ == "__main__":
    main()
