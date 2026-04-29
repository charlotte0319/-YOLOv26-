"""
tests/test_detection_analyzer.py

作用：
- 校验 `inference_pipeline.detection_analyzer` 的行数推断与批量统计行为。

调用关系：
- 由 `pytest` 自动执行。
- 使用 DummyResult/DummyBoxes 模拟 YOLO 输出，覆盖关键边界场景。
"""

from pathlib import Path

import pytest

from inference_pipeline import detection_analyzer as analyzer


class DummyTensor:
    def __init__(self, data):
        self._data = data

    def tolist(self):
        return self._data

    def __len__(self):
        return len(self._data)


class DummyBoxes:
    def __init__(self, xyxy, cls, conf):
        self.xyxy = DummyTensor(xyxy)
        self.cls = DummyTensor(cls)
        self.conf = DummyTensor(conf)

    def __len__(self):
        return len(self.xyxy)


class DummyResult:
    def __init__(self, shape, boxes, path=None):
        self.orig_shape = shape
        self.boxes = boxes
        self.path = path


def build_result(row_specs=None, path="test.jpg", shape=(1080, 1920)):
    xyxy = []
    cls = []
    conf = []

    if row_specs is None:
        row_specs = [{"y": 80 + i * 120, "products": 8, "empties": 0} for i in range(5)]

    for spec in row_specs:
        y = spec["y"]
        product_count = spec.get("products", 0)
        empty_count = spec.get("empties", 0)

        for index in range(product_count):
            x1 = 50 + index * 100
            y1 = y
            x2 = x1 + 60
            y2 = y + 50
            xyxy.append([x1, y1, x2, y2])
            cls.append(0)
            conf.append(0.9)

        for index in range(empty_count):
            x1 = 60 + index * 140
            y1 = y + 5
            x2 = x1 + 55
            y2 = y + 45
            xyxy.append([x1, y1, x2, y2])
            cls.append(1)
            conf.append(0.92)

    boxes = DummyBoxes(xyxy, cls, conf)
    return DummyResult(shape, boxes, path=path)


def test_detect_rows_basic():
    result = build_result(path="basic.jpg")
    record = analyzer.analyze_single(result)
    assert record["n_rows"] == 5


def test_detect_rows_keeps_sparse_empty_row():
    row_specs = [
        {"y": 80, "products": 8, "empties": 0},
        {"y": 200, "products": 8, "empties": 0},
        {"y": 320, "products": 0, "empties": 3},
        {"y": 440, "products": 8, "empties": 0},
        {"y": 560, "products": 8, "empties": 0},
    ]
    result = build_result(row_specs=row_specs, path="sparse-empty.jpg")
    record = analyzer.analyze_single(result)

    assert record["n_rows"] == 5
    assert any(record.get(f"row{index}_empty", 0) >= 3 for index in range(1, 6))


def test_analyze_all_prefers_result_path_over_external_list():
    result = build_result(path="real.jpg")
    records = analyzer.analyze_all([result], [Path("wrong.jpg")])
    assert records[0]["file"] == "real.jpg"


def test_analyze_single_requires_path_information_when_result_has_no_path():
    result = build_result(path=None)
    with pytest.raises(ValueError):
        analyzer.analyze_single(result)


def test_batch_padding_capacity():
    records = [
        {"n_rows": 3, "row1_product": 1},
        {"n_rows": 5, "row1_product": 1},
    ]
    analyzer.pad_row_columns(records, row_capacity=6)
    assert all("row6_ratio" in record for record in records)


def test_detect_rows_can_exceed_20_when_image_has_more_shelves():
    row_specs = [{"y": 40 + i * 90, "products": 8, "empties": 0} for i in range(21)]
    result = build_result(row_specs=row_specs, path="many-rows.jpg", shape=(2400, 1920))

    record = analyzer.analyze_single(result)

    assert record["n_rows"] == 21


def test_build_record_from_box_groups_matches_standard_schema():
    product_boxes = [
        (100.0, 100.0, 0, 0.95, 50.0),
        (220.0, 100.0, 0, 0.95, 50.0),
        (100.0, 260.0, 0, 0.95, 50.0),
    ]
    empty_boxes = [
        (220.0, 260.0, 1, 1.0, 50.0),
    ]

    record = analyzer.build_record_from_box_groups(
        file_name="legacy.jpg",
        img_shape=(480, 640),
        product_boxes=product_boxes,
        empty_boxes=empty_boxes,
    )

    assert record["file"] == "legacy.jpg"
    assert record["product_count"] == 3
    assert record["empty_count"] == 1
    assert record["total"] == 4
    assert record["n_rows"] == 2
    assert record["row1_product"] == 2
    assert record["row2_product"] == 1
    assert record["row2_empty"] == 1
