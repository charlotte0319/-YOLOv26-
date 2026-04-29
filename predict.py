"""
predict.py

作用：
- 加载训练好的权重，对测试目录图片执行批量推理。
- 调用 inference_pipeline 完成统计分析并导出 CSV。

实现方式：
- run_inference() 负责模型推理与结果图保存。
- 推理阶段即完成逐张统计，最后统一补齐行字段并导出 CSV。
- 推理结果优先使用 YOLO 返回的 `result.path` 绑定文件名，避免目录流式推理时发生错位。

关键函数：
- build_predict_kwargs(input_dir, device)：集中维护推理参数。
- run_inference(input_dir)：返回 records。
- main()：完整推理流程入口。

调用方式：
- python predict.py
"""

import gc
import logging
import sys
import traceback
from pathlib import Path

from tqdm import tqdm

from inference_pipeline.csv_exporter import export_csv
from inference_pipeline.detection_analyzer import analyze_single, finalize_records
from inference_pipeline.run_artifacts import save_stage_snapshot
from project_config import (
    BEST_PT,
    NN_CSV_DIR,
    PREDICT_HALF,
    PREDICT_IMG_DIR,
    PREDICT_IMGSZ,
    PREDICT_SAVE_IMAGES,
    TEST_IMAGE_DIR,
    TRAIN_PREDICT_VERSION,
    can_enable_half_precision,
    init_project,
    normalize_worker_count,
    resolve_yolo_device,
)

IMG_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff"}
RESULT_CLASS_NAMES = {0: "", 1: "空缺"}
# PREDICT_SAVE_IMAGES = True ,project_config中控制手动保存开关
line_width = 5
font_size = 28
show_labels = True
show_conf = True


def build_predict_kwargs(input_source: Path | list[Path], device: str | int) -> dict:
    """返回推理参数，关键运行项由配置统一控制。"""
    source = str(input_source) if isinstance(input_source, Path) else [str(path) for path in input_source]
    return {
        "workers": normalize_worker_count(),
        "source": source,
        "imgsz": PREDICT_IMGSZ,
        "conf": 0.45,
        "iou": 0.5,
        "max_det": 1000,
        "device": device,
        "project": str(PREDICT_IMG_DIR.parent),
        "name": PREDICT_IMG_DIR.name,
        "exist_ok": True,
        "verbose": False,
        "batch": 1,
        "half": can_enable_half_precision(device),
        "stream": True,
    }


def run_inference(input_dir: Path = TEST_IMAGE_DIR) -> list[dict]:
    """执行模型推理并直接返回分析记录，避免缓存整批结果导致内存上涨。"""
    from ultralytics import YOLO
    from ultralytics.utils import LOGGER as YOLO_LOGGER

    print("[推理] 开始加载权重...", flush=True)
    model = YOLO(str(BEST_PT))
    model.model.names = RESULT_CLASS_NAMES
    device = resolve_yolo_device(probe_runtime=True)

    print(f"[推理] 当前版本：{TRAIN_PREDICT_VERSION}", flush=True)
    print(f"[推理] 使用权重：{BEST_PT}", flush=True)
    print(f"[推理] 使用设备：{device}", flush=True)

    image_paths = sorted(path for path in input_dir.glob("*") if path.suffix.lower() in IMG_SUFFIXES)
    if not image_paths:
        print(f"[推理] 未在目录中发现可用图片：{input_dir}")
        return []

    total = len(image_paths)
    image_paths_by_name = {path.name: path for path in image_paths}
    print(f"[推理] 共发现 {total} 张图片，开始批量推理。", flush=True)
    print(
        f"[推理] 推理尺寸：{PREDICT_IMGSZ}，线程数：{normalize_worker_count()}，"
        f"半精度：{can_enable_half_precision(device)}，保存结果图：{PREDICT_SAVE_IMAGES}，"
        "推理模式：batch=1 流式处理",
        flush=True,
    )

    records: list[dict] = []
    pbar = tqdm(total=total, desc="推理进度", unit="张", ncols=100, leave=True, file=sys.stdout)
    predict_kwargs = build_predict_kwargs(input_dir, device)

    try:
        previous_level = YOLO_LOGGER.level
        YOLO_LOGGER.setLevel(logging.ERROR)
        try:
            prediction_stream = model.predict(**predict_kwargs)
            for image_index, result in enumerate(prediction_stream):
                result_path = Path(str(getattr(result, "path", ""))) if getattr(result, "path", None) else None
                source_path = image_paths_by_name.get(result_path.name) if result_path is not None else None
                if source_path is None and image_index < len(image_paths):
                    source_path = image_paths[image_index]
                result.names = RESULT_CLASS_NAMES
                if source_path is not None:
                    # 某些输入模式下 Ultralytics 会把结果路径写成 image0.jpg 这类占位名。
                    # 这里强制回填真实源图路径，后续 CSV 绑定使用原文件名。
                    result.path = str(source_path)
                    if PREDICT_SAVE_IMAGES:
                        PREDICT_IMG_DIR.mkdir(parents=True, exist_ok=True)
                        result.plot(
                            save=True,
                            filename=str(PREDICT_IMG_DIR / source_path.name),
                            line_width=line_width,
                            font_size=font_size,
                            conf=show_conf,
                            labels=show_labels,
                        )
                records.append(analyze_single(result, source_path))
                pbar.update(1)

                if (image_index + 1) % 50 == 0:
                    gc.collect()
                    try:
                        import torch

                        if torch.cuda.is_available():
                            torch.cuda.empty_cache()
                    except Exception:
                        pass
        finally:
            YOLO_LOGGER.setLevel(previous_level)
    finally:
        pbar.close()

    print("[推理] 推理阶段完成。")
    print(f"[推理] 结果图目录：{PREDICT_IMG_DIR}")
    return finalize_records(records)


def print_prediction_summary(records: list[dict]) -> None:
    """打印批量推理结果摘要，便于终端查看与截图。"""
    if not records:
        return

    total_images = len(records)
    total_products = sum(int(record.get("product_count", 0) or 0) for record in records)
    total_empty = sum(int(record.get("empty_count", 0) or 0) for record in records)
    avg_empty_ratio = sum(float(record.get("empty_ratio", 0) or 0) for record in records) / total_images
    avg_rows = sum(int(record.get("n_rows", 0) or 0) for record in records) / total_images

    highest_empty_ratio = max(records, key=lambda record: float(record.get("empty_ratio", 0) or 0))
    highest_empty_count = max(records, key=lambda record: int(record.get("empty_count", 0) or 0))

    print("[统计] 推理结果摘要")
    print("-" * 64)
    print(f"总图片数          : {total_images}")
    print(f"商品总数          : {total_products}")
    print(f"空缺总数          : {total_empty}")
    print(f"平均空缺率        : {avg_empty_ratio:.2%}")
    print(f"平均有效层数      : {avg_rows:.2f}")
    print("-" * 64)
    print(
        f"空缺率最高样本    : {highest_empty_ratio.get('file', '')} "
        f"-> {float(highest_empty_ratio.get('empty_ratio', 0) or 0):.2%}"
    )
    print(
        f"空缺数最高样本    : {highest_empty_count.get('file', '')} "
        f"-> {int(highest_empty_count.get('empty_count', 0) or 0)}"
    )


def main() -> None:
    """推理 + 分析 + 导出 的总入口。"""
    print("[流程] 货架空缺检测流程启动。")
    init_project(stage="predict")

    try:
        runtime_device = resolve_yolo_device(probe_runtime=True)
        save_stage_snapshot(
            NN_CSV_DIR / "predict_runtime_snapshot.json",
            stage="predict",
            extra={
                "weight_path": str(BEST_PT),
                "input_dir": str(TEST_IMAGE_DIR),
                "device": str(runtime_device),
                "imgsz": PREDICT_IMGSZ,
                "workers": normalize_worker_count(),
                "half": can_enable_half_precision(runtime_device),
                "predict_half_config": PREDICT_HALF,
                "predict_save_images": PREDICT_SAVE_IMAGES,
            },
        )

        records = run_inference()
        if not records:
            print("[流程] 没有可分析结果，流程结束。")
            return

        print_prediction_summary(records)
        print("[导出] 开始写入 CSV 结果。")
        export_csv(records)

        save_stage_snapshot(
            NN_CSV_DIR / "predict_completion_snapshot.json",
            stage="predict_complete",
            extra={"record_count": len(records), "predict_image_dir": str(PREDICT_IMG_DIR)},
        )

        print("[流程] 全部任务执行完成。")
    except Exception as exc:
        print(f"[错误] 流程执行失败：{exc}")
        traceback.print_exc()
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
