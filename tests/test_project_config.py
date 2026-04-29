"""
tests/test_project_config.py

作用：
- 校验配置模块 `project_config.py` 的路径、设备和快照行为。

调用关系：
- 由 `pytest` 自动执行。
- 覆盖训练 YAML 重定向、设备解析、半精度开关与运行快照语义。
"""


import pytest
import yaml

import project_config


def test_get_training_yaml_path_keeps_source_yaml_unchanged(tmp_path, monkeypatch):
    source_yaml = tmp_path / "dataset.yaml"
    source_yaml.write_text("path: D:/old/data\ntrain: images/train\n", encoding="utf-8")
    data_path = tmp_path / "dataset"
    data_path.mkdir()
    runtime_yaml = tmp_path / ".runtime_dataset.yaml"

    monkeypatch.setattr(project_config, "YAML_PATH", source_yaml)
    monkeypatch.setattr(project_config, "DATA_PATH", data_path)
    monkeypatch.setattr(project_config, "RUNTIME_YAML_PATH", runtime_yaml)

    resolved_path = project_config.get_training_yaml_path()

    assert resolved_path == runtime_yaml
    assert "D:/old/data" in source_yaml.read_text(encoding="utf-8")
    runtime_cfg = yaml.safe_load(runtime_yaml.read_text(encoding="utf-8"))
    assert runtime_cfg["path"] == str(data_path).replace("\\", "/")


def test_get_training_yaml_path_reuses_source_yaml_when_path_matches(tmp_path, monkeypatch):
    data_path = tmp_path / "dataset"
    data_path.mkdir()
    normalized_data_path = str(data_path).replace("\\", "/")
    source_yaml = tmp_path / "dataset.yaml"
    source_yaml.write_text(f"path: {normalized_data_path}\ntrain: images/train\n", encoding="utf-8")
    runtime_yaml = tmp_path / ".runtime_dataset.yaml"

    monkeypatch.setattr(project_config, "YAML_PATH", source_yaml)
    monkeypatch.setattr(project_config, "DATA_PATH", data_path)
    monkeypatch.setattr(project_config, "RUNTIME_YAML_PATH", runtime_yaml)

    resolved_path = project_config.get_training_yaml_path()

    assert resolved_path == source_yaml
    assert not runtime_yaml.exists()


def test_normalize_worker_count_clamps_to_cpu_count(monkeypatch):
    monkeypatch.setattr(project_config, "CPU_COUNT", 4)
    monkeypatch.setattr(project_config, "YOLO_WORKERS", 16)
    assert project_config.normalize_worker_count() == 4


def test_resolve_yolo_device_prefers_env_value(monkeypatch):
    project_config.resolve_yolo_device.cache_clear()
    monkeypatch.setattr(project_config, "YOLO_DEVICE", "cpu")
    assert project_config.resolve_yolo_device() == "cpu"
    project_config.resolve_yolo_device.cache_clear()


def test_resolve_yolo_device_returns_none_without_probe_or_override(monkeypatch):
    project_config.resolve_yolo_device.cache_clear()
    monkeypatch.setattr(project_config, "YOLO_DEVICE", "")
    assert project_config.resolve_yolo_device() is None
    project_config.resolve_yolo_device.cache_clear()


def test_can_enable_half_precision_disables_cpu_and_respects_switch(monkeypatch):
    monkeypatch.setattr(project_config, "PREDICT_HALF", True)
    assert project_config.can_enable_half_precision("cpu") is False
    assert project_config.can_enable_half_precision(None) is False
    assert project_config.can_enable_half_precision(0) is True

    monkeypatch.setattr(project_config, "PREDICT_HALF", False)
    assert project_config.can_enable_half_precision(0) is False


def test_runtime_snapshot_keeps_runtime_device_unknown_without_probe(monkeypatch):
    project_config.resolve_yolo_device.cache_clear()
    monkeypatch.setattr(project_config, "YOLO_DEVICE", "0")
    monkeypatch.setattr(project_config, "PREDICT_HALF", True)
    monkeypatch.setattr(project_config, "LOAD_LAST", False)

    snapshot = project_config.runtime_snapshot()

    assert snapshot["configured_device"] == "0"
    assert snapshot["runtime_device"] == "unknown"
    assert snapshot["runtime_device_probed"] is False
    assert snapshot["predict_half_active"] is True
    assert snapshot["timezone"] == "Asia/Shanghai"
    assert snapshot["load_last"] is False
    project_config.resolve_yolo_device.cache_clear()


def test_env_int_returns_default_on_non_numeric_value(monkeypatch):
    monkeypatch.setenv("YOLOV26_TEST_PORT", "abc")
    result = project_config.env_int("YOLOV26_TEST_PORT", 5000)
    assert result == 5000


def test_validate_prediction_paths_checks_best_weight(tmp_path, monkeypatch):
    data_path = tmp_path / "data"
    test_dir = data_path / "images" / "test"
    test_dir.mkdir(parents=True)
    best_pt = tmp_path / "best.pt"

    monkeypatch.setattr(project_config, "DATA_PATH", data_path)
    monkeypatch.setattr(project_config, "TEST_IMAGE_DIR", test_dir)
    monkeypatch.setattr(project_config, "BEST_PT", best_pt)

    with pytest.raises(FileNotFoundError):
        project_config.validate_prediction_paths()


def test_validate_model_family_rejects_unknown_value(monkeypatch):
    monkeypatch.setattr(project_config, "ACTIVE_MODEL_FAMILY", "yolo26z")

    with pytest.raises(ValueError):
        project_config.validate_model_family()


def test_validate_model_selection_rejects_mismatched_base_model(monkeypatch):
    monkeypatch.setattr(project_config, "ACTIVE_MODEL_FAMILY", "yolo26x")
    monkeypatch.setattr(project_config, "MODEL_NAME", "yolo26n.pt")
    monkeypatch.setattr(project_config, "LOAD_LAST", False)

    with pytest.raises(ValueError):
        project_config.validate_model_selection()
