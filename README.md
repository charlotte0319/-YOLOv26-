# YOLOv26 货架空缺检测项目
## 一眼看懂

```text
数据集 + YAML
    -> train.py
    -> best.pt
    -> predict.py
    -> analysis_results.csv
    -> Web 看板 / 离线评估
```

- 新环境第一步：`Copy-Item .env.example .env`
- 当前默认起步配置已经对齐：`yolo26n`、`LOAD_LAST=False`、`v1`
- 当前最重要的中间产物：`runs_yolo26*/analysis/csv_*/analysis_results.csv`
- 如果你只是想把项目跑通，先看“快速开始”
- 如果你要接手代码结构，再读 `development.md`

## 适用范围

这个项目当前适合：

- 单机实验
- 本地维护

这个项目当前不适合：

- 多用户协作系统
- 公网生产环境
- 复杂运维治理
- 云端弹性部署

当前主流程已经闭环：

- 使用 Ultralytics YOLO 训练检测模型
- 对测试图片批量推理
- 统计每张图的商品数、空缺数、空缺率和层数
- 导出统一的 `analysis_results.csv`
- 用 Flask Web 看板展示结果
- 用离线评估脚本将预测 CSV 和人工标注 CSV 对比

## 文档分工

- `README.md`
  面向使用者，回答“怎么配置、怎么运行、结果在哪里”
- `development.md`
  面向开发者，回答“代码怎么读、模块怎么分层、后续怎么维护”

建议阅读顺序：

1. 先读 `README.md`
2. 再读 `development.md`
3. 最后打开 `project_config.py` 看当前实验配置

## 快速开始

### 1. 准备环境

建议环境：

- Python：`3.12`
- Ruff 目标版本：`py312`

安装依赖：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

如果你只运行训练、推理和看板，`requirements-dev.txt` 可以先不装。

### 2. 初始化配置

```powershell
Copy-Item .env.example .env
```

当前 `.env.example` 与 `project_config.py` 的默认值已经对齐，核心起步配置是：

```text
YOLOV26_ACTIVE_MODEL_FAMILY=yolo26n
YOLOV26_LOAD_LAST=False
YOLOV26_BASE_VERSION=v1
YOLOV26_TRAIN_PREDICT_VERSION=v1
YOLOV26_MODEL_NAME=yolo26n.pt
```

复制后，优先检查这些字段：

- `YOLOV26_ACTIVE_MODEL_FAMILY`
- `YOLOV26_LOAD_LAST`
- `YOLOV26_BASE_VERSION`
- `YOLOV26_TRAIN_PREDICT_VERSION`
- `YOLOV26_MODEL_NAME`
- `YOLOV26_YAML_NAME`
- `YOLOV26_DATA_NAME`

### 3. 训练

```powershell
python train.py
```

### 4. 推理并导出分析 CSV

```powershell
python predict.py
```

### 5. 启动看板

开发模式：

```powershell
python web_dashboard/app.py
```

本地 WSGI 模式：

```powershell
python wsgi.py
```

默认访问地址：

```text
http://127.0.0.1:5000
```

## 主流程

```text
configs/*.yaml + data/*
    -> train.py
    -> runs_yolo26*/train_weights/train_*/weights/best.pt
    -> predict.py
    -> runs_yolo26*/predict_images/
    -> runs_yolo26*/analysis/csv_*/analysis_results.csv
    -> web_dashboard/ 或 evaluation/evaluate_predictions.py
```

你只需要先记住三件事：

1. `train.py` 负责产出当前版本的 `best.pt`
2. `predict.py` 不只做检测，还负责业务统计和 CSV 导出
3. 看板和离线评估主要都依赖 `analysis_results.csv`

## 项目结构

下面只列日常真正需要关心的目录和文件：

```text
yolov26/
|-- project_config.py
|-- train.py
|-- predict.py
|-- wsgi.py
|-- configs/
|-- data/
|-- model/
|-- inference_pipeline/
|-- web_dashboard/
|-- evaluation/
|-- tests/
|-- scripts/
|-- runs_yolo26n/
|-- runs_yolo26x/
|-- data_preprocessing/
|-- model_fusion/
`-- legacy_physics_stockout/
```

按日常使用频率理解：

- `project_config.py`
  项目统一配置中心，决定模型、数据、参数和派生路径
- `train.py`
  训练入口，只负责组织参数并调用 YOLO 训练
- `predict.py`
  推理入口，负责批量推理、逐图统计、逐层统计和 CSV 导出
- `inference_pipeline/`
  推理后处理模块，负责业务统计、CSV 导出和运行快照
- `web_dashboard/`
  Flask 看板，负责页面、API 和训练产物展示
- `evaluation/`
  离线评估脚本
- `tests/`
  覆盖配置解析、推理参数、检测统计、CSV 导出、离线评估和看板接口的回归测试
- `scripts/`
  包含本地质量检查、全流程自检、开发/生产模式看板启动脚本，以及 `scripts/maintenance/` 下的低频维护工具

这些目录可以先不当成主入口：

- `data_preprocessing/`
- `model_fusion/`
- `legacy_physics_stockout/`

## 数据与 YAML

### 默认位置

- 数据目录：`data/stock_out`
- 训练 YAML：`configs/SKU110K.yaml`

### 当前最小数据结构

```text
data/stock_out/
|-- images/
|   |-- train/
|   |-- val/
|   `-- test/
`-- labels/
    |-- train/
    `-- val/
```

先记住这三点：

- 训练至少依赖 `images/train`、`images/val` 和对应标签
- 推理默认读取 `images/test`
- `labels/test` 不是当前主流程硬要求

### YAML 的当前设计

`configs/SKU110K.yaml` 当前约定：

- `path` 使用相对路径
- `names` 明确为 `0=商品`、`1=空缺`
- `download` 钩子只负责把 SKU110K 风格 CSV 转成商品类标签，不负责自动生成空缺类标签

`project_config.py` 里的 `get_training_yaml_path()` 会做两件事：

- 如果 YAML 里的 `path` 和当前 `DATA_PATH` 等价，直接使用原 YAML
- 只有真正不一致时，才生成 `.runtime_*.yaml` 作为运行时副本

## 常改配置

### 实验切换相关

- `YOLOV26_ACTIVE_MODEL_FAMILY`
  决定当前使用 `runs_yolo26n` 还是 `runs_yolo26x`
- `YOLOV26_LOAD_LAST`
  是否从上一轮训练权重继续训练
- `YOLOV26_BASE_VERSION`
  当 `LOAD_LAST=True` 时，上一轮训练版本号
- `YOLOV26_TRAIN_PREDICT_VERSION`
  当前这轮训练和推理的版本号
- `YOLOV26_MODEL_NAME`
  首次训练时使用的基础模型文件名
- `YOLOV26_YAML_NAME`
  当前训练用的 YAML 文件名
- `YOLOV26_DATA_NAME`
  当前数据目录名

### 运行参数相关

- `YOLOV26_DEVICE`
  训练和推理设备，留空表示自动探测
- `YOLOV26_TRAIN_IMGSZ`
  训练图像尺寸
- `YOLOV26_TRAIN_EPOCHS`
  训练轮数
- `YOLOV26_TRAIN_BATCH`
  训练 batch
- `YOLOV26_PREDICT_IMGSZ`
  推理图像尺寸
- `YOLOV26_DASHBOARD_PORT`
  看板端口
- `YOLOV26_SKIP_CONFIG_VALIDATION`
  测试或不完整环境下跳过路径校验

完整配置仍以 `project_config.py` 为准。

### 首次训练推荐配置

```text
YOLOV26_LOAD_LAST=False
YOLOV26_MODEL_NAME=yolo26n.pt 或 yolo26x.pt
YOLOV26_TRAIN_PREDICT_VERSION=v1
```

### 续训推荐配置

```text
YOLOV26_LOAD_LAST=True
YOLOV26_BASE_VERSION=v1
YOLOV26_RESUME_NAME=best.pt
YOLOV26_TRAIN_PREDICT_VERSION=v2
```

## 常用命令

训练：

```powershell
python train.py
```

推理并导出 CSV：

```powershell
python predict.py
```

启动看板：

```powershell
python web_dashboard/app.py
python wsgi.py
```

启动脚本：

```powershell
powershell -File scripts/start_dashboard_dev.ps1
powershell -File scripts/start_dashboard_prod.ps1
```

离线评估：

```powershell
python evaluation/evaluate_predictions.py --pred runs_yolo26n/analysis/csv_v1/analysis_results.csv --gt path/to/ground_truth.csv
```

如果你当前用的是 `yolo26x` 或其他版本，请把命令中的路径改成你实际生成的 CSV。

## 输入与输出

主要输入：

- 基础模型：`model/`
- 数据集：`data/<DATA_NAME>/`
- 训练 YAML：`configs/<YAML_NAME>`

主要输出：

- 训练输出：`runs_yolo26*/train_weights/train_<version>/`
- 推理结果图：`runs_yolo26*/predict_images/`
- 分析 CSV：`runs_yolo26*/analysis/csv_<version>/analysis_results.csv`
- 评估报告：`evaluation_reports/`

训练输出里常见内容：

- `weights/best.pt`
- `results.csv`
- `results.png`
- `confusion_matrix*.png`
- `train_runtime_snapshot.json`
- `train_completion_snapshot.json`

这里最重要的是：

```text
runs_yolo26*/analysis/csv_<version>/analysis_results.csv
```

因为：

- 看板读取它
- 离线评估读取它
- 业务统计结果也以它为准

## 常见问题

### 新环境一训练就报权重路径不存在

优先检查：

1. 是否已经复制 `.env.example` 为 `.env`
2. 当前 `.env` 是否为首次训练配置
3. `model/` 下是否存在对应基础模型文件

### 训练启动时报路径不存在

优先检查：

- `data/stock_out` 是否存在
- `configs/SKU110K.yaml` 是否存在
- 若为续训，上一轮 `best.pt` 是否存在

### 看板打开后没有数据

优先检查：

- 是否已经运行过 `python predict.py`
- `runs_yolo26*/analysis/csv_*/analysis_results.csv` 是否已生成
- 当前 `.env` 中的模型族和版本号，是否和已生成目录一致

### 测试环境没有完整数据或权重

可以临时跳过配置路径校验：

```powershell
$env:YOLOV26_SKIP_CONFIG_VALIDATION = "1"
```

### PowerShell 能 import，脚本启动却找不到模块

通常是因为新进程没有继承你当前虚拟环境。优先做法：

- 先激活 `.venv`
- 或直接使用 `scripts/` 下提供的启动脚本
