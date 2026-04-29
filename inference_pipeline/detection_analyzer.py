"""
inference_pipeline/detection_analyzer.py

作用：
- 对 YOLO 推理结果做业务统计：商品数、空缺数、空缺率、行级统计。
- 稳定估计货架行数，尽量避免把 5 行识别成 1 行或 11 行。

实现方式：
- 将商品框与高置信空缺框同时作为行检测证据，而不是只依赖商品框。
- 采用“加权核密度投影 + 峰值检测 + 1D KMeans 细化中心 + 大间距补层”的四阶段方案。
- 批量分析时优先使用 YOLO 返回的 `result.path` 绑定图片名，避免文件名错位。
- 对全批次记录补齐到统一行容量（max_rows + 1），避免 Web 展示字段缺失。

关键函数：
- detect_rows(product_boxes, empty_boxes, img_h)
- analyze_single(result, image_path=None)
- analyze_all(results, image_paths=None)

调用方式：
- from inference_pipeline.detection_analyzer import analyze_all
"""

from pathlib import Path
import re

import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import find_peaks

from inference_pipeline.run_artifacts import now_beijing_str
from project_config import CLASS_EMPTY, CLASS_PRODUCT, ROW_COUNT_CAP

PLACEHOLDER_RESULT_NAME = re.compile(r"^image\d+\.(jpg|jpeg|png|bmp|webp|tiff)$", re.IGNORECASE)


def now_hms() -> str:
    """返回北京时间 HH:MM:SS。"""
    return now_beijing_str("%H:%M:%S")


def estimate_spacing(centers: np.ndarray, median_h: float) -> float:
    """估计相邻货架行间距，用于峰值最小距离约束。"""
    if centers.size < 2:
        return max(median_h, 8.0)

    sorted_centers = np.sort(centers)
    diffs = np.diff(sorted_centers)
    valid = diffs[diffs > max(2.0, median_h * 0.35)]
    if valid.size == 0:
        return max(median_h, 8.0)
    return float(np.median(valid))


def merge_close_peaks(peaks: np.ndarray, density: np.ndarray, merge_gap: int) -> np.ndarray:
    """合并过近峰值，防止同一行被切成多行。"""
    if peaks.size <= 1:
        return peaks

    merged = [int(peaks[0])]
    for peak in peaks[1:]:
        if peak - merged[-1] >= merge_gap:
            merged.append(int(peak))
            continue
        if density[int(peak)] > density[merged[-1]]:
            merged[-1] = int(peak)
    return np.array(sorted(merged), dtype=int)


def merge_close_centers(centers: np.ndarray, min_gap: float) -> np.ndarray:
    """合并距离过近的中心点，避免重复层。"""
    if centers.size <= 1:
        return centers

    merged = [float(np.sort(centers)[0])]
    for center in np.sort(centers)[1:]:
        center = float(center)
        if center - merged[-1] < min_gap:
            merged[-1] = (merged[-1] + center) / 2.0
        else:
            merged.append(center)
    return np.array(merged, dtype=float)


def refine_centers_with_kmeans(
    centers_y: np.ndarray,
    init_centers: np.ndarray,
    weights: np.ndarray | None = None,
    max_iter: int = 30,
) -> np.ndarray:
    """对峰值中心进行 1D KMeans 细化。"""
    refined = np.array(sorted(init_centers.astype(float)))
    if refined.size == 0:
        return refined

    point_weights = np.ones_like(centers_y, dtype=float) if weights is None else np.array(weights, dtype=float)

    for _ in range(max_iter):
        dist = np.abs(centers_y[:, None] - refined[None, :])
        labels = np.argmin(dist, axis=1)

        new_centers = refined.copy()
        for idx in range(len(refined)):
            cluster = centers_y[labels == idx]
            cluster_weights = point_weights[labels == idx]
            if cluster.size > 0:
                new_centers[idx] = float(np.average(cluster, weights=cluster_weights))

        new_centers = np.array(sorted(new_centers))
        if np.allclose(new_centers, refined, atol=0.25):
            refined = new_centers
            break
        refined = new_centers

    return refined


def infer_missing_centers(centers: np.ndarray, reference_spacing: float, max_rows: int) -> np.ndarray:
    """当相邻两层间距异常偏大时，补出可能遗漏的中间层。"""
    if centers.size < 2 or reference_spacing <= 0:
        return centers

    inferred = [float(np.sort(centers)[0])]
    sorted_centers = np.sort(centers)
    for left, right in zip(sorted_centers[:-1], sorted_centers[1:]):
        gap = float(right - left)
        ratio = gap / reference_spacing if reference_spacing > 0 else 1.0
        if ratio > 1.85 and len(inferred) < max_rows:
            missing_count = max(0, min(int(round(ratio)) - 1, 3))
            step = gap / (missing_count + 1) if missing_count else 0.0
            for index in range(missing_count):
                if len(inferred) >= max_rows:
                    break
                inferred.append(float(left + step * (index + 1)))
        if len(inferred) < max_rows:
            inferred.append(float(right))

    return np.array(sorted(inferred[:max_rows]), dtype=float)


def centers_to_rows(centers: np.ndarray, img_h: int, median_h: float) -> list[tuple[float, float]]:
    """将行中心转换为行区间。"""
    if centers.size == 0:
        return []

    centers = np.array(sorted(centers))
    midpoints = (centers[:-1] + centers[1:]) / 2 if centers.size > 1 else np.array([])
    bounds = np.concatenate(([0.0], midpoints, [float(img_h)]))

    pad = max(1.0, median_h * 0.30)
    rows = []
    for idx in range(len(bounds) - 1):
        lower = float(bounds[idx])
        upper = float(bounds[idx + 1])
        y_min = max(0.0, lower - pad)
        y_max = min(float(img_h), upper + pad)
        if y_max - y_min >= max(2.0, median_h * 0.35):
            rows.append((y_min, y_max))
    return rows


def build_row_evidence(
    product_boxes: list[tuple],
    empty_boxes: list[tuple],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """构造行检测证据，商品框为主，空缺框为辅。"""
    evidence: list[tuple[float, float, float]] = []

    for _, cy, _, conf, height in product_boxes:
        weight = float(np.clip(max(conf, 0.60), 0.60, 1.25))
        evidence.append((float(cy), float(max(1.0, height)), weight))

    for _, cy, _, conf, height in empty_boxes:
        weight = float(np.clip(max(conf, 0.45) * 0.75, 0.30, 0.90))
        evidence.append((float(cy), float(max(1.0, height)), weight))

    if not evidence:
        return np.array([]), np.array([]), np.array([])

    centers_y = np.array([item[0] for item in evidence], dtype=float)
    heights = np.array([item[1] for item in evidence], dtype=float)
    weights = np.array([item[2] for item in evidence], dtype=float)
    return centers_y, heights, weights


def detect_rows(product_boxes: list[tuple], empty_boxes: list[tuple], img_h: int) -> list[tuple[float, float]]:
    """基于商品框和空缺框稳健估计货架行区间。"""
    img_h = max(int(img_h), 1)
    centers_y, heights, weights = build_row_evidence(product_boxes, empty_boxes)
    if centers_y.size == 0:
        return []

    median_h = float(np.median(heights)) if heights.size else max(8.0, img_h * 0.03)
    y_axis = np.arange(img_h, dtype=float)
    sigma = float(np.clip(median_h * 0.35, 2.0, max(6.0, img_h * 0.03)))

    density = np.zeros(img_h, dtype=float)
    for center, height, weight in zip(centers_y, heights, weights):
        height_weight = float(np.clip(height / max(median_h, 1e-6), 0.6, 1.4))
        density += weight * height_weight * np.exp(-0.5 * ((y_axis - center) / sigma) ** 2)

    # 阶段 1：在 y 轴构建平滑密度，得到候选层中心峰值。
    density = gaussian_filter1d(density, sigma=max(1.0, sigma * 0.20))
    if float(np.max(density)) <= 0:
        return []

    spacing = estimate_spacing(centers_y, median_h)
    min_distance = int(max(6.0, median_h * 0.75, spacing * 0.55))
    prominence = max(float(np.max(density)) * 0.09, 0.5)

    peak_result = find_peaks(density, distance=min_distance, prominence=prominence)
    peaks = np.asarray(peak_result[0], dtype=np.intp)
    peaks = merge_close_peaks(peaks, density, merge_gap=int(max(3.0, median_h * 0.60)))

    if peaks.size == 0:
        return [(0.0, float(img_h))]

    estimated_row_cap = max(1, int(round(img_h / max(median_h * 0.85, 1.0))))
    max_reasonable_rows = min(estimated_row_cap, ROW_COUNT_CAP) if ROW_COUNT_CAP > 0 else estimated_row_cap
    if peaks.size > max_reasonable_rows:
        peak_scores = density[np.asarray(peaks, dtype=np.intp)]
        top_idx = np.argsort(peak_scores)[-max_reasonable_rows:]
        peaks = np.sort(peaks[top_idx])

    # 阶段 2：1D KMeans 细化峰值中心，减少单层分裂/错位。
    refined_centers = refine_centers_with_kmeans(centers_y, peaks.astype(float), weights=weights)
    refined_spacing = estimate_spacing(refined_centers if refined_centers.size > 1 else centers_y, median_h)

    # 阶段 3：大间距补层 + 近邻合并，抑制漏层和重复层。
    refined_centers = infer_missing_centers(refined_centers, max(spacing, refined_spacing), max_reasonable_rows)
    refined_centers = merge_close_centers(refined_centers, min_gap=max(4.0, median_h * 0.55))

    rows = centers_to_rows(refined_centers, img_h, median_h)
    return rows if rows else [(0.0, float(img_h))]


def resolve_image_path(result, fallback_path: Path | str | None = None) -> Path:
    """优先使用模型返回的结果路径绑定文件名，必要时回退到外部传入路径。"""
    result_path = getattr(result, "path", None)
    if result_path:
        resolved = Path(result_path)
        if fallback_path is not None and PLACEHOLDER_RESULT_NAME.fullmatch(resolved.name):
            return Path(fallback_path)
        return resolved
    if fallback_path is not None:
        return Path(fallback_path)
    raise ValueError("推理结果缺少图片路径，无法绑定输出文件名。")


def find_row(cy: float, rows: list[tuple[float, float]]) -> int:
    """返回目标所属最近行索引。"""
    if not rows:
        return 0
    centers = np.array([(y_min + y_max) / 2 for y_min, y_max in rows], dtype=float)
    return int(np.argmin(np.abs(centers - cy)))


def build_record_from_box_groups(
    file_name: str,
    img_shape: tuple[int, ...],
    product_boxes: list[tuple],
    empty_boxes: list[tuple],
) -> dict:
    """基于已归一化的商品框/空缺框生成统一统计记录。"""
    img_h = int(img_shape[0]) if img_shape else 0
    if not product_boxes and not empty_boxes:
        return {
            "timestamp": now_hms(),
            "file": file_name,
            "product_count": 0,
            "empty_count": 0,
            "total": 0,
            "empty_ratio": 0.0,
            "n_rows": 0,
        }

    rows = detect_rows(product_boxes, empty_boxes, img_h)
    if not rows:
        rows = [(0.0, float(max(img_h, 1)))]

    row_stats = {idx: {"product": 0, "empty": 0} for idx in range(len(rows))}

    for _, cy, _, _, _ in product_boxes:
        row_stats[find_row(cy, rows)]["product"] += 1
    for _, cy, _, _, _ in empty_boxes:
        row_stats[find_row(cy, rows)]["empty"] += 1

    product_count = len(product_boxes)
    empty_count = len(empty_boxes)
    total = product_count + empty_count
    empty_ratio = round(empty_count / total, 4) if total else 0.0

    record = {
        "timestamp": now_hms(),
        "file": file_name,
        "product_count": product_count,
        "empty_count": empty_count,
        "total": total,
        "empty_ratio": empty_ratio,
        "n_rows": len(rows),
    }

    for row_index in range(len(rows)):
        product = row_stats[row_index]["product"]
        empty = row_stats[row_index]["empty"]
        ratio = round(empty / (product + empty), 4) if (product + empty) > 0 else 0.0
        row_no = row_index + 1
        record[f"row{row_no}_product"] = product
        record[f"row{row_no}_empty"] = empty
        record[f"row{row_no}_ratio"] = ratio

    return record


def analyze_single(result, image_path: Path | str | None = None) -> dict:
    """分析单张图片推理结果并返回统计字典。"""
    resolved_path = resolve_image_path(result, image_path)
    img_h, img_w = result.orig_shape
    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        return {
            "timestamp": now_hms(),
            "file": resolved_path.name,
            "product_count": 0,
            "empty_count": 0,
            "total": 0,
            "empty_ratio": 0.0,
            "n_rows": 0,
        }

    product_boxes = []
    empty_boxes = []
    for box, cls_id, conf in zip(boxes.xyxy.tolist(), boxes.cls.tolist(), boxes.conf.tolist()):
        x1, y1, x2, y2 = box
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2
        width = max(1.0, (x2 - x1))
        height = max(1.0, (y2 - y1))
        area_ratio = (width * height) / max(float(img_w * img_h), 1.0)

        if int(cls_id) == CLASS_PRODUCT:
            product_boxes.append((cx, cy, int(cls_id), float(conf), float(height)))
        elif int(cls_id) == CLASS_EMPTY:
            if conf > 0.40 and 0.0005 < area_ratio < 0.15:
                empty_boxes.append((cx, cy, int(cls_id), float(conf), float(height)))

    return build_record_from_box_groups(
        file_name=resolved_path.name,
        img_shape=(img_h, img_w),
        product_boxes=product_boxes,
        empty_boxes=empty_boxes,
    )


def pad_row_columns(records: list[dict], row_capacity: int) -> None:
    """将每条记录补齐到统一行字段，避免前端字段缺失。"""
    for record in records:
        for row_no in range(1, row_capacity + 1):
            record.setdefault(f"row{row_no}_product", 0)
            record.setdefault(f"row{row_no}_empty", 0)
            record.setdefault(f"row{row_no}_ratio", 0.0)


def finalize_records(records: list[dict]) -> list[dict]:
    """补齐批次级行字段并打印汇总信息。"""
    max_rows = max((int(record.get("n_rows", 0)) for record in records), default=0)
    row_capacity = max_rows + 1 if max_rows > 0 else 1

    for record in records:
        record["max_rows_detected"] = max_rows
        record["row_capacity"] = row_capacity

    pad_row_columns(records, row_capacity)

    print(f"[分析] 本批次最大检测行数：{max_rows}")
    print(f"[分析] 网页展示行容量（含缓冲）：{row_capacity}")
    print("[分析] 统计阶段完成。")
    return records


def analyze_all(results: list, image_paths: list[Path] | None = None) -> list[dict]:
    """批量分析并打印每张图概要。"""
    total = len(results)
    print(f"[分析] 开始统计，共 {total} 张图片。")

    records = []
    for index, result in enumerate(results, start=1):
        fallback_path = image_paths[index - 1] if image_paths and index - 1 < len(image_paths) else None
        resolved_path = resolve_image_path(result, fallback_path)
        if fallback_path is not None and getattr(result, "path", None):
            fallback_name = Path(fallback_path).name
            if resolved_path.name != fallback_name:
                print(f"[分析] 检测到结果路径与输入列表不一致，已采用模型返回路径：{resolved_path.name}")

        record = analyze_single(result, resolved_path)
        records.append(record)

        print(
            f"[分析] {index}/{total} {resolved_path.name} | 商品:{record['product_count']:3d} "
            f"空缺:{record['empty_count']:3d} | 行数:{record['n_rows']:2d} | 空缺率:{record['empty_ratio']:.1%}"
        )

    return finalize_records(records)
