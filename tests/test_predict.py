"""
tests/test_predict.py

作用：
- 校验 `predict.py` 的推理参数构建和异常退出行为。

调用关系：
- 由 `pytest` 自动执行。
- 通过 monkeypatch 隔离外部依赖，验证主流程控制逻辑。
"""

import pytest

import predict


def test_build_predict_kwargs_uses_runtime_device_and_half_switch(monkeypatch, tmp_path):
    monkeypatch.setattr(predict, "PREDICT_IMGSZ", 704)
    monkeypatch.setattr(predict, "PREDICT_IMG_DIR", tmp_path / "predict_images")
    monkeypatch.setattr(predict, "normalize_worker_count", lambda: 3)
    monkeypatch.setattr(predict, "can_enable_half_precision", lambda device: device != "cpu")

    kwargs = predict.build_predict_kwargs([tmp_path / "a.jpg"], device="cpu")

    assert kwargs["imgsz"] == 704
    assert kwargs["workers"] == 3
    assert kwargs["half"] is False
    assert kwargs["source"] == [str(tmp_path / "a.jpg")]


def test_predict_main_exits_with_non_zero_code_on_failure(monkeypatch):
    monkeypatch.setattr(predict, "init_project", lambda stage="predict": None)
    monkeypatch.setattr(predict, "resolve_yolo_device", lambda probe_runtime=False: "cpu")
    monkeypatch.setattr(predict, "normalize_worker_count", lambda: 1)
    monkeypatch.setattr(predict, "can_enable_half_precision", lambda _device: False)
    monkeypatch.setattr(predict, "save_stage_snapshot", lambda *args, **kwargs: None)

    def fake_run_inference():
        raise RuntimeError("boom")

    monkeypatch.setattr(predict, "run_inference", fake_run_inference)

    with pytest.raises(SystemExit) as exc_info:
        predict.main()

    assert exc_info.value.code == 1
