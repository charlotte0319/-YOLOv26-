"""
legacy_physics_stockout/geometry_stockout_monitor.py

作用：
- 使用历史几何规则方案进行空缺可视化与 CSV 统计导出（保留参考，不作为主流程）。

实现方式：
- 先用 YOLO 推理获得商品框。
- 调用 geometry_stockout_logic 推断空缺槽位。
- 将商品框与空缺框画到图片后保存，并导出 missing 数量统计。

关键函数：
- run_stockout_monitor()

调用方式：
- python legacy_physics_stockout/geometry_stockout_monitor.py
"""

from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm
from ultralytics import YOLO

from legacy_physics_stockout.geometry_stockout_logic import ShelfAnalysis
from inference_pipeline.csv_exporter import export_csv
from inference_pipeline.detection_analyzer import build_record_from_box_groups, finalize_records
from project_config import (
    BEST_PT,
    CLASS_EMPTY,
    CLASS_PRODUCT,
    STOCKOUT_IMG_DIR,
    STOCKOUT_SENSITIVITY,
    STOCKOUT_STATS_PATH,
    TEST_IMAGE,
    init_project,
)


def tensor_to_list(value) -> list:
    """兼容 Ultralytics Tensor/ndarray/list，统一转成 Python 列表。"""
    if value is None:
        return []
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


def collect_product_boxes(result) -> tuple[np.ndarray, list[tuple[float, float, int, float, float]]]:
    """只提取商品框，避免把模型预测空缺混进几何推断输入。"""
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return np.empty((0, 4), dtype=float), []

    product_xyxy: list[list[float]] = []
    product_boxes: list[tuple[float, float, int, float, float]] = []
    xyxy_list = tensor_to_list(boxes.xyxy)
    cls_list = tensor_to_list(boxes.cls)
    conf_list = tensor_to_list(boxes.conf)

    for box, cls_id, conf in zip(xyxy_list, cls_list, conf_list):
        if int(cls_id) != CLASS_PRODUCT:
            continue

        x1, y1, x2, y2 = [float(value) for value in box]
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        height = max(1.0, y2 - y1)

        product_xyxy.append([x1, y1, x2, y2])
        product_boxes.append((cx, cy, CLASS_PRODUCT, float(conf), float(height)))

    if not product_xyxy:
        return np.empty((0, 4), dtype=float), []
    return np.array(product_xyxy, dtype=float), product_boxes


def convert_missing_boxes(missing_slots: list[list[float]]) -> list[tuple[float, float, int, float, float]]:
    """把几何法空缺槽位转换成统一统计所需的空缺框格式。"""
    empty_boxes: list[tuple[float, float, int, float, float]] = []
    for cx, cy, _, h in missing_slots:
        empty_boxes.append((float(cx), float(cy), CLASS_EMPTY, 1.0, float(max(1.0, h))))
    return empty_boxes


def run_stockout_monitor() -> None:
    """运行几何法空缺分析并输出图像与 CSV。"""
    init_project(stage="predict")
    STOCKOUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    STOCKOUT_STATS_PATH.parent.mkdir(parents=True, exist_ok=True)

    print("[历史几何] 开始执行历史方案（仅参考）。")
    print(f"[历史几何] 加载权重：{BEST_PT}")
    model = YOLO(str(BEST_PT))

    image_paths = list(Path(TEST_IMAGE).glob("*.jpg"))
    print(f"[历史几何] 待处理图片数：{len(image_paths)}")

    results = model.predict(source=str(TEST_IMAGE), imgsz=640, conf=0.3, iou=0.5, verbose=False, stream=True)

    all_stats = []
    for index, result in enumerate(tqdm(results, total=len(image_paths), desc="历史几何分析", unit="张"), start=1):
        image_draw = result.orig_img.copy()
        product_xyxy, product_boxes = collect_product_boxes(result)

        for box in product_xyxy:
            cv2.rectangle(
                image_draw,
                (int(box[0]), int(box[1])),
                (int(box[2]), int(box[3])),
                (0, 255, 0),
                1,
            )

        missing = ShelfAnalysis.get_stockout_results(product_xyxy, result.orig_img.shape, sensitivity=STOCKOUT_SENSITIVITY)
        empty_boxes = convert_missing_boxes(missing)

        for cx, cy, w, h in missing:
            x1, y1 = int(cx - w / 2), int(cy - h / 2)
            x2, y2 = int(cx + w / 2), int(cy + h / 2)
            cv2.rectangle(image_draw, (x1, y1), (x2, y2), (0, 0, 255), 2)
            cv2.putText(image_draw, "X", (int(cx - 5), int(cy + 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

        result_path = getattr(result, "path", None)
        output_name = Path(result_path).name if result_path else f"legacy_{index:05d}.jpg"
        cv2.imwrite(str(STOCKOUT_IMG_DIR / output_name), image_draw)
        all_stats.append(
            build_record_from_box_groups(
                file_name=output_name,
                img_shape=result.orig_img.shape,
                product_boxes=product_boxes,
                empty_boxes=empty_boxes,
            )
        )

    export_csv(finalize_records(all_stats), csv_path=STOCKOUT_STATS_PATH)
    print(f"[历史几何] 分析完成，CSV 已保存：{STOCKOUT_STATS_PATH}")


if __name__ == "__main__":
    run_stockout_monitor()
