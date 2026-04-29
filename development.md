# 工程说明

> 面向接手开发、继续维护和做结构调整的人  
> 更新时间：2026-04-01

## 一眼看懂

如果你今天要接手这个项目，先按下面顺序看代码：

1. `project_config.py`
2. `train.py`
3. `predict.py`
4. `inference_pipeline/detection_analyzer.py`
5. `web_dashboard/__init__.py`
6. `web_dashboard/services/`
7. `evaluation/evaluate_predictions.py`
8. `tests/`

原因很简单：先看配置和入口，再看推理后处理，最后再看展示层和测试。

## 这份文档解决什么问题

这份文档主要回答四个问题：

1. 当前项目的主链路是什么
2. 代码应该按什么顺序阅读
3. 每个模块各自负责什么
4. 后续继续迭代时，边界应该怎么守

如果你现在的目标是先把项目跑起来，请先读 `README.md`。

## 当前主链路

```text
project_config.py
    -> train.py
    -> predict.py
        -> inference_pipeline/detection_analyzer.py
        -> inference_pipeline/csv_exporter.py
    -> web_dashboard/
    -> evaluation/evaluate_predictions.py
```

再展开一点就是：

```text
数据集 + YAML
    -> 训练入口 train.py
    -> 训练权重 best.pt
    -> 推理入口 predict.py
    -> 逐图 / 逐层统计
    -> analysis_results.csv
    -> Web 看板展示
    -> 离线评估脚本对比人工标注
```

理解这个项目时，不要一开始就钻进某个局部模块。  
先把整条链路看清，再分别进入训练、推理、展示和评估。

## 推荐读码顺序

### 先看 `project_config.py`

第一次看这个文件，先回答这些问题：

- 当前用哪套模型族
- 当前是首次训练还是续训
- 数据目录在哪里
- 当前版本号是什么
- 当前训练输出写到哪里
- 当前推理权重从哪里读
- 当前 CSV 输出到哪里

建议按这些区块去读：

- 模型与数据
- 训练参数
- 推理参数
- 看板参数
- 派生路径
- legacy 路径
- 分析与看板路径
- 校验与初始化函数

### 再看 `train.py`

读 `train.py` 时只抓三件事：

- 训练前做了哪些初始化
- 训练参数从哪里来
- 训练产物写到哪里

核心流程：

```text
init_project(stage="train")
    -> configure_runtime()
    -> get_training_yaml_path()
    -> resolve_yolo_device()
    -> build_train_kwargs()
    -> YOLO(str(MODEL_PATH))
    -> model.train(**train_kwargs)
```

### 然后看 `predict.py`

读 `predict.py` 的重点不是“怎么跑检测”，而是“怎么把检测结果变成业务统计结果”。

核心流程：

```text
init_project(stage="predict")
    -> 保存 predict_runtime_snapshot.json
    -> run_inference()
    -> analyze_single(result)
    -> finalize_records(records)
    -> export_csv(records)
    -> 保存 predict_completion_snapshot.json
```

### 再进入 `inference_pipeline/`

这里是推理后处理的真正核心。

- `detection_analyzer.py`
  把 YOLO 框转成商品数、空缺数、层数和逐层统计
  第一次重点看：`analyze_single()`、`detect_rows()`、`finalize_records()`
- `csv_exporter.py`
  导出统一结构的 `analysis_results.csv`
  第一次重点看：字段顺序和异常处理
- `run_artifacts.py`
  集中负责训练/推理阶段快照 JSON 的写入，以及北京时间/时区相关工具
  第一次重点看：`save_stage_snapshot()`、`now_beijing_str()` 和快照写入时机

### 最后看展示层、评估和测试

建议顺序：

1. `web_dashboard/__init__.py`
2. `web_dashboard/services/`
3. `web_dashboard/data_service.py`
4. `web_dashboard/templates/page.html`
5. `web_dashboard/static/js/`
6. `evaluation/evaluate_predictions.py`
7. `tests/`

其中 `web_dashboard/data_service.py` 不是新逻辑入口，而是兼容门面。  
第一次看到它时，只需要确认两点：

- 它仍然被旧测试和旧导入路径使用
- 实际业务实现已经迁到 `web_dashboard/services/`

## 模块地图

下面不是完整仓库树，而是“日常维护真正有意义的结构图”：

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

按职责分层看：

- 主流程
  `project_config.py`、`train.py`、`predict.py`、`inference_pipeline/`、`web_dashboard/`、`evaluation/`、`tests/`、`scripts/`
  日常训练、推理、展示、评估都围绕这些模块展开
- 辅助但非高频
  `data_preprocessing/`、`model_fusion/`
  有参考价值，但不属于日常主链路
- 历史保留
  `legacy_physics_stockout/`
  旧几何法方案，只保留参考意义

## `project_config.py` 怎么理解

### 它在项目中的角色

`project_config.py` 负责的不是业务逻辑，而是“运行边界”：

- 读环境变量
- 提供默认值
- 派生路径
- 校验关键输入路径
- 创建运行目录
- 生成运行快照所需配置
- 处理训练 YAML 的运行时副本

### 当前配置组织方式

这个文件当前已经按阅读顺序分块：

1. 模型与数据
2. 训练参数
3. 推理参数
4. 看板参数
5. 派生路径
6. legacy 路径
7. 分析与看板路径
8. 业务常量
9. 初始化与校验函数

这样做的好处：

- `train.py` 只取训练相关配置
- `predict.py` 只取推理和分析相关配置
- `web_dashboard/` 只取展示和路径相关配置
- 路径来源集中，后续排查更容易

### 当前配置优先级

```text
系统环境变量
    -> .env
    -> project_config.py 内置默认值
```

当前仓库已经对齐到同一套起步默认值：

- `.env.example` 和 `project_config.py` 默认值一致
- 默认模型族为 `yolo26n`
- 默认是首次训练配置：`LOAD_LAST=False`
- 默认版本号为 `v1`

因此日常建议仍然是：

1. 先复制 `.env.example` 为 `.env`
2. 以 `.env` 作为本地实验入口配置
3. 只在确实需要时再覆盖环境变量

### 初始化与校验规则

当前约定是：

- 导入 `project_config.py` 时，不做危险副作用
- 真正的目录创建和路径校验放到 `init_project()`
- 训练、推理、看板入口都应该先调用 `init_project()`

这样可以避免：

- import 时意外创建目录
- import 时因为环境不完整直接失败
- 各入口初始化逻辑不一致

## 入口层职责

- `train.py`
  初始化训练环境、组装训练参数、启动 YOLO 训练
  关键点：`configure_runtime()`、`build_train_kwargs()`、`main()`
- `predict.py`
  加载 `best.pt`、批量推理、调用后处理、导出分析 CSV
  关键点：`build_predict_kwargs()`、`run_inference()`、`main()`
- `web_dashboard/app.py`
  本地开发模式入口
  关键点：直接调用 `run_dev_server()`
- `wsgi.py`
  WSGI 标准入口，同时支持直接执行启动 Waitress
  关键点：创建 app 前先 `init_project(stage="dashboard")`

### `predict.py` 当前实现上值得注意的点

- 推理使用 `batch=1 + stream=True` 的流式处理
- 结果优先用 YOLO 返回的 `result.path` 绑定原图
- 运行过程中会定期执行 `gc.collect()`
- 有 CUDA 时会尝试 `torch.cuda.empty_cache()`

## `web_dashboard/` 的分层

### 路由层

`web_dashboard/__init__.py` 当前承担：

- Flask app factory
- 页面路由
- API 路由
- 错误处理
- 健康检查

当前页面路由：

- `/`
- `/records`
- `/training`
- `/cases`
- `/system`

当前主要 API：

- `/api/dashboard`
- `/api/records`
- `/api/cases`
- `/api/system`
- `/api/training`
- `/api/data`
- `/api/summary`
- `/api/image/<filename>`
- `/api/train-asset/<filename>`
- `/healthz`

### 服务层

- `csv_reader.py`
  读分析 CSV，并做字段整理
- `records_service.py`
  搜索、筛选、排序、分页、风险分级
- `training_service.py`
  读取训练结果和训练图表资产
- `analytics_service.py`
  构建案例分析页数据
- `system_service.py`
  构建系统状态页数据

当前维护原则：

- 路由层只做参数解析和响应封装
- 业务逻辑放服务层
- 不再把新逻辑堆回旧门面文件

### 兼容层

- `web_dashboard/data_service.py`
  保留旧导入路径的兼容门面
- 只转发 `web_dashboard/services/` 的导出
- 新逻辑不要继续写回这里

### 前端层

当前前端结构分三层：

- 入口层：`static/js/app.js`
- 公共层：`api.js`、`state.js`、`utils.js`、`renderers.js`、`modal.js`
- 页面层：`static/js/pages/*.js`

对应原则：

- 页面只初始化自己需要的逻辑
- 公共状态和公共渲染逻辑集中维护
- 页面间不要重复造相同工具

## 评估、测试与脚本

### 评估

`evaluation/evaluate_predictions.py` 负责：

- 读取预测 CSV
- 读取人工标注 CSV
- 按 `file` 对齐
- 计算误差指标
- 输出 JSON 和 Markdown 报告

当前核心指标：

- `row_accuracy`
- `row_mae`
- `empty_count_mae`
- `product_count_mae`
- `empty_ratio_mae`

### 测试

当前测试按模块拆分为 7 个文件：

- `test_project_config.py`
- `test_predict.py`
- `test_detection_analyzer.py`
- `test_csv_exporter.py`
- `test_evaluate_predictions.py`
- `test_dashboard_data_service.py`
- `test_dashboard_app.py`

这些测试主要保护：

- 配置解析
- 推理参数
- 行数检测与补齐
- CSV 导出
- 评估逻辑
- Dashboard 路由和数据服务

如果你第一次接手，建议按下面的顺序理解：

- `test_project_config.py`
  保护环境变量、路径派生和初始化校验，是理解配置边界的入口
- `test_predict.py`
  保护推理参数构建、批量推理主流程和异常退出行为
- `test_detection_analyzer.py`
  保护行检测、空缺统计、记录补齐等核心业务逻辑
- `test_csv_exporter.py`
  保护 `analysis_results.csv` 的字段、顺序和导出兼容性
- `test_evaluate_predictions.py`
  保护预测 CSV 与人工标注 CSV 的离线对比逻辑
- `test_dashboard_data_service.py`
  保护看板服务层的数据聚合、筛选、排序和分页
- `test_dashboard_app.py`
  保护 Flask 页面路由、API 输出和错误处理

### 脚本

高频脚本：

- `quality_check.ps1`
  本地质量检查入口，顺序执行 Ruff 和 Pytest
- `run_all.ps1`
  全流程自检入口，先做 `compileall`，再按需执行 Pytest
- `start_dashboard_dev.ps1`
  用 Flask 开发模式启动看板，适合本地调界面和接口
- `start_dashboard_prod.ps1`
  启动本地 WSGI 模式看板

低频维护脚本：

- `maintenance/archive_training_run.py`
  归档一次训练产物目录，便于整理历史实验结果
- `maintenance/rename_weight_classes.py`
  修正权重内嵌类别名称，避免推理显示名异常

当前脚本已统一为：

- 优先使用项目内 `.venv\Scripts\python.exe`
- 不再写死具体的 `runs_* / train_*` 路径
- 优先跟随当前配置的 `TRAIN_OUT_DIR`、`BEST_PT` 和看板端口

## 主流程与历史目录的边界

当前日常工作的核心目录：

- `project_config.py`
- `train.py`
- `predict.py`
- `inference_pipeline/`
- `web_dashboard/`
- `evaluation/`
- `tests/`
- `scripts/`

不应当再当成主入口的目录：

- `data_preprocessing/`
- `model_fusion/`
- `legacy_physics_stockout/`

这些目录可以保留参考价值，但不应该继续往里面加当前主流程的新能力。

## 后续维护约定

1. 新配置先进入 `project_config.py`，不要再引入第二套主配置中心。
2. 新入口仍然先调 `init_project()`，保持初始化顺序一致。
3. 新的 Dashboard 后端逻辑写进 `web_dashboard/services/`，不要堆回兼容层。
4. 新的前端页面逻辑写进 `web_dashboard/static/js/pages/`，公共能力放公共模块。
5. 低频维护脚本继续放在 `scripts/maintenance/`。
6. 历史目录只做兼容和参考，不再承担新主流程功能。
7. 训练和推理阶段继续保留快照 JSON，便于复盘。
8. 修改数据集 YAML 时，优先保持相对路径，不要把源码 YAML 改回本机绝对路径。

## 接手时最先做的事

1. 先读 `README.md`，把运行闭环看明白。
2. 打开 `project_config.py`，确认当前模型族、版本号、数据目录和输出目录。
3. 读 `train.py` 和 `predict.py`，理解训练和推理入口。
4. 读 `inference_pipeline/detection_analyzer.py`，理解业务统计逻辑。
5. 读 `web_dashboard/__init__.py` 和 `web_dashboard/services/`，理解展示层。
6. 最后看 `tests/`，确认当前哪些行为已经被保护。

这样理解速度最快，也最不容易被历史目录和旧实验信息带偏。
