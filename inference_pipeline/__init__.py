"""
inference_pipeline 包

作用：
- 承载推理后处理能力，包括行数分析、CSV 导出和运行快照产物记录。

调用来源：
- `predict.py` 在推理完成后调用。
- 测试模块通过 `from inference_pipeline import ...` 引用。
"""
