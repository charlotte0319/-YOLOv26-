"""
legacy_physics_stockout/geometry_stockout_logic.py

作用：
- 基于几何规则在货架检测框中推断可能的空缺槽位（历史方案，精度有限，仅保留参考）。

实现方式：
- 对检测框按 x 坐标排序。
- 在“可能同一行”的相邻目标间根据间距估算空缺数量。
- 使用局部斜率补偿空缺框 y 偏移，适应斜视角。

关键函数：
- ShelfAnalysis.get_stockout_results(boxes, img_shape, sensitivity)

调用方式：
- 被 geometry_stockout_monitor.py 调用。
"""

import numpy as np


class ShelfAnalysis:
    """几何规则货架空缺推断工具类。"""

    @staticmethod
    def get_stockout_results(boxes, img_shape, sensitivity=0.8):
        """
        根据目标框估计空缺槽位。

        参数：
        - boxes: Nx4，xyxy。
        - img_shape: 图像形状（保留参数，保持调用兼容）。
        - sensitivity: 灵敏度，越高越容易判空缺。

        返回：
        - missing_slots: List[[cx, cy, w, h], ...]
        """
        if len(boxes) < 2:
            return []

        img_h, img_w = img_shape[:2]
        sorted_idx = np.argsort(boxes[:, 0])
        boxes = boxes[sorted_idx]

        missing_slots = []
        assigned = np.zeros(len(boxes), dtype=bool)

        for i in range(len(boxes)):
            if assigned[i]:
                continue

            assigned[i] = True
            last_x2 = boxes[i][2]
            last_y2 = boxes[i][3]
            avg_h = boxes[i][3] - boxes[i][1]
            avg_w = boxes[i][2] - boxes[i][0]

            for j in range(i + 1, len(boxes)):
                if assigned[j]:
                    continue

                box_j = boxes[j]
                y_diff = box_j[3] - last_y2
                x_dist = box_j[0] - last_x2

                max_allowed_y_drift = (x_dist * 0.2) + (avg_h * 0.15)
                if 0 < x_dist < (avg_w * 4) and abs(y_diff) < max_allowed_y_drift:
                    gap_width = x_dist
                    if gap_width > avg_w * (1.5 - sensitivity):
                        num_empty = int(round(gap_width / avg_w))
                        num_empty = max(1, min(num_empty, 6))

                        slope = y_diff / x_dist if x_dist > 0 else 0
                        for n in range(num_empty):
                            m_cx = last_x2 + (gap_width / num_empty) * (n + 0.5)
                            offset_y = (m_cx - last_x2) * slope
                            m_cy = (last_y2 + offset_y) - (avg_h / 2)
                            m_cx = float(np.clip(m_cx, 0, max(img_w - 1, 0)))
                            m_cy = float(np.clip(m_cy, 0, max(img_h - 1, 0)))
                            missing_slots.append([m_cx, m_cy, avg_w, avg_h])

                    last_x2 = box_j[2]
                    last_y2 = box_j[3]
                    assigned[j] = True
                    avg_w = (avg_w + (box_j[2] - box_j[0])) / 2
                    avg_h = (avg_h + (box_j[3] - box_j[1])) / 2

        return missing_slots
