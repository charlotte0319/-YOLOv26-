"""
project_config.py

作用：
- 统一管理模型选择、训练参数、推理参数、看板参数和派生路径。
- 支持默认值配置，也支持通过环境变量覆盖，便于本地运行与后续部署。

实现方式：
- 按模块分组：模型与数据、训练参数、推理参数、看板参数、派生路径、legacy 路径、分析与看板路径、业务常量。
- 运行时优先读取环境变量，再回退到默认值。
- 初始化阶段按 train / predict / dashboard 场景做路径校验。
- 训练阶段如需修正数据集 YAML 中的 `path`，只生成运行时副本，不改写源码配置。

调用方式：
- 代码中：from project_config import XXX
- 命令行：python train.py / python predict.py / python web_dashboard/app.py / python wsgi.py
"""

import os
from functools import lru_cache
from pathlib import Path

import yaml

from inference_pipeline.run_artifacts import BEIJING_TZ_NAME

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 可选依赖
    load_dotenv = None

if callable(load_dotenv):
    load_dotenv()

ROOT = Path(__file__).parent.resolve()  # 项目根目录；所有相对路径都从这里派生
SKIP_CONFIG_VALIDATION = os.getenv("YOLOV26_SKIP_CONFIG_VALIDATION", "0") == "1"  # 用于测试/空环境跳过路径校验；由 train.py / predict.py / web_dashboard 启动前生效
CPU_COUNT = max(1, os.cpu_count() or 1)  # 当前机器 CPU 核心数；供 worker 上限收敛使用


def env_str(name: str, default: str) -> str:
    """读取字符串环境变量。"""
    value = os.getenv(name)
    return value if value not in (None, "") else default


def env_bool(name: str, default: bool) -> bool:
    """读取布尔环境变量。"""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    """读取整数环境变量。"""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# ========================= 模型与数据 =========================
# 这一组参数决定“当前跑哪套模型、读哪份数据、输出写到哪一版”。
# 主要被 train.py、predict.py、wsgi.py、web_dashboard/__init__.py 和 runtime_snapshot() 使用。
# 阅读顺序：
#   1. 先决定当前模型族 ACTIVE_MODEL_FAMILY
#   2. 再决定冷启动用哪份基础模型 MODEL_NAME
#   3. 再决定是否沿用上一轮权重 LOAD_LAST
#   4. 最后决定版本号 TRAIN_PREDICT_VERSION / BASE_VERSION
#
# 模型族总开关：
#   ACTIVE_MODEL_FAMILY="yolo26n"
#       -> 使用 yolo26n
#       -> 使用 runs_yolo26n
#       -> 训练输出写到 runs_yolo26n/train_weights
#       -> 推理输出写到 runs_yolo26n/predict_images
#   ACTIVE_MODEL_FAMILY="yolo26x"
#       -> 使用 yolo26x
#       -> 使用 runs_yolo26x
#       -> 训练输出写到 runs_yolo26x/train_weights
#       -> 推理输出写到 runs_yolo26x/predict_images
ACTIVE_MODEL_FAMILY = env_str("YOLOV26_ACTIVE_MODEL_FAMILY", "yolo26x")     # 当前模型族；决定整套 runs、训练、推理、分析目录落到 n 还是 x
MODEL_NAME = env_str("YOLOV26_MODEL_NAME", "yolo26n.pt")                    # 冷启动训练时从 model/ 下读取的基础模型文件名
LOAD_LAST = env_bool("YOLOV26_LOAD_LAST", False)                            # 是否沿用上一轮训练权重做本轮初始化；False 读 model/，True 读 runs/train_<BASE_VERSION>/weights/
BASE_VERSION = env_str("YOLOV26_BASE_VERSION", "v1")                        # 上一轮训练版本；仅在 LOAD_LAST=True 时使用
RESUME_NAME = env_str("YOLOV26_RESUME_NAME", "best.pt")                     # 沿用上一轮训练时读取的权重文件名，通常是 best.pt
TRAIN_PREDICT_VERSION = env_str("YOLOV26_TRAIN_PREDICT_VERSION", "v5")      # 当前训练/推理批次版本；用于输出目录命名和看板展示
YAML_NAME = env_str("YOLOV26_YAML_NAME", "SKU110K.yaml")                    # 当前训练使用的 YAML 文件名；get_training_yaml_path() 会读取它
DATA_NAME = env_str("YOLOV26_DATA_NAME", "SKU110K_fixed")                   # 当前主数据目录名；拼接为 data/<DATA_NAME>
# 使用说明：
#   首次训练：
#       LOAD_LAST=False
#       MODEL_NAME="yolo26n.pt" 或 "yolo26x.pt"
#       TRAIN_PREDICT_VERSION="v1"
#   沿用上一轮权重继续训练：
#       LOAD_LAST=True
#       BASE_VERSION="v1"
#       RESUME_NAME="best.pt"
#       TRAIN_PREDICT_VERSION="v2"

# ========================= 训练参数 =========================
# 这一组参数只影响 train.py，不参与推理和看板逻辑。
TRAIN_IMGSZ = env_int("YOLOV26_TRAIN_IMGSZ", 800)                           # 训练图像尺寸；train.py -> build_train_kwargs()
TRAIN_EPOCHS = env_int("YOLOV26_TRAIN_EPOCHS", 100)                         # 训练总 epoch；写入 TRAIN_STATIC_KWARGS
TRAIN_BATCH = env_int("YOLOV26_TRAIN_BATCH", 16)                            # 训练 batch size；写入 TRAIN_STATIC_KWARGS
TRAIN_PATIENCE = env_int("YOLOV26_TRAIN_PATIENCE", 40)                      # 早停 patience；写入 TRAIN_STATIC_KWARGS

# train.py -> model.train(**kwargs) 的基础参数。
TRAIN_BASE_KWARGS = {
    "epochs": TRAIN_EPOCHS,
    "batch": TRAIN_BATCH,
    "patience": TRAIN_PATIENCE,
    "cache": "ram",
    "optimizer": "Adamw",
    "momentum": 0.937,
    "weight_decay": 0.0005,
    "lr0": 0.00005,
    "lrf": 0.01,
    "cos_lr": True,
    "amp": True,
    "deterministic": False,
    "plots": True,
    "save_period": -1,
    "exist_ok": True,
    "verbose": True,
}

# train.py -> model.train(**kwargs) 的增强和损失权重参数。
TRAIN_AUG_KWARGS = {
    "mosaic": 1.0,
    "close_mosaic": 30,
    "mixup": 0.1,
    "fliplr": 0.5,
    "hsv_h": 0.010,
    "hsv_s": 0.5,
    "hsv_v": 0.4,
    "translate": 0.1,
    "scale": 0.7,
    "box": 8.0,
    "cls": 0.5,
}

TRAIN_STATIC_KWARGS = {**TRAIN_BASE_KWARGS, **TRAIN_AUG_KWARGS}              # train.py -> build_train_kwargs() -> model.train(**kwargs)

# ========================= 推理参数 =========================
# 这一组参数只影响 predict.py 和 detection_analyzer.py。
YOLO_DEVICE = env_str("YOLOV26_DEVICE", "")                                 # 训练/推理共用设备配置；resolve_yolo_device() 优先读取它
YOLO_WORKERS = env_int("YOLOV26_WORKERS", min(16, CPU_COUNT))               # 训练 DataLoader / 推理 worker 期望值；normalize_worker_count() 会再收敛
PREDICT_IMGSZ = env_int("YOLOV26_PREDICT_IMGSZ", 640)                       # 推理图像尺寸；predict.py -> build_predict_kwargs()
PREDICT_HALF = env_bool("YOLOV26_PREDICT_HALF", True)                       # 是否允许半精度；predict.py -> can_enable_half_precision()
PREDICT_SAVE_IMAGES = env_bool("YOLOV26_PREDICT_SAVE_IMAGES", True)         # 是否保存预测结果图；predict.py -> model.predict(save=...)
ROW_COUNT_CAP = env_int("YOLOV26_ROW_COUNT_CAP", 0)                         # 可选最大行数上限；detection_analyzer.py 使用，0 表示动态估计

# ========================= 看板参数 =========================
# 这一组参数只影响 web_dashboard。
DASHBOARD_HOST = env_str("YOLOV26_DASHBOARD_HOST", "0.0.0.0")               # Web 服务监听地址；web_dashboard/app.py 和 wsgi.py 使用
DASHBOARD_PORT = env_int("YOLOV26_DASHBOARD_PORT", 5000)                    # Web 服务监听端口；web_dashboard/app.py 和 wsgi.py 使用
DASHBOARD_DEBUG = env_bool("YOLOV26_DASHBOARD_DEBUG", False)                # Flask 开发模式是否开启 debug；web_dashboard/app.py 使用
DASHBOARD_RECORD_LIMIT = env_int("YOLOV26_DASHBOARD_RECORD_LIMIT", 120)     # 总览页默认最多返回多少条记录；web_dashboard/__init__.py 使用

# ========================= 派生路径 =========================
# 这一组把上面的配置具体落成文件系统路径，供 train.py、predict.py、web_dashboard、evaluation 共用。
# 阅读顺序：
#   1. 先看 ACTIVE_MODEL_FAMILY 决定 RUNS_DIR 落到 runs_yolo26n 还是 runs_yolo26x
#   2. 再看 LOAD_LAST 决定 MODEL_PATH 读历史权重还是 model/ 基础模型
#   3. 再看 TRAIN_PREDICT_VERSION 决定当前训练输出目录、推理权重目录和分析 CSV 目录
#
# 结果路径：
#   训练初始化权重：MODEL_PATH
#   当前训练输出目录：TRAIN_OUT_DIR
#   当前推理权重：BEST_PT
#   当前推理结果图目录：PREDICT_IMG_DIR
#   当前分析 CSV 目录：NN_CSV_DIR
RUNS_YOLO26N_DIR = ROOT / "runs_yolo26n"  # yolo26n 全部运行产物根目录
RUNS_YOLO26X_DIR = ROOT / "runs_yolo26x"  # yolo26x 全部运行产物根目录

if ACTIVE_MODEL_FAMILY == "yolo26n":
    RUNS_DIR = RUNS_YOLO26N_DIR                 # 当前选择 yolo26n，全部训练/推理/分析输出写到 runs_yolo26n
elif ACTIVE_MODEL_FAMILY == "yolo26x":
    RUNS_DIR = RUNS_YOLO26X_DIR                 # 当前选择 yolo26x，全部训练/推理/分析输出写到 runs_yolo26x
else:
    RUNS_DIR = ROOT / "runs_invalid"            # 非法值占位；真实错误由 validate_model_family() 抛出

DATA_PATH = ROOT / "data" / DATA_NAME           # 当前主数据目录；训练和推理都会从这里派生输入路径
YAML_PATH = ROOT / "configs" / YAML_NAME        # 源码中的数据集 YAML 路径；get_training_yaml_path() 读取它
RUNTIME_YAML_PATH = ROOT / "configs" / f".runtime_{YAML_NAME}"  # 仅在 YAML path 不匹配时生成的运行时副本

MODEL_PATH = (
    RUNS_DIR / "train_weights" / f"train_{BASE_VERSION}" / "weights" / RESUME_NAME
    if LOAD_LAST
    else ROOT / "model" / MODEL_NAME
)  # 训练初始化权重路径；先看 ACTIVE_MODEL_FAMILY 选 runs，再看 LOAD_LAST 决定读历史权重还是 model/ 基础模型

TRAIN_OUT_DIR = RUNS_DIR / "train_weights" / f"train_{TRAIN_PREDICT_VERSION}"  # 当前训练输出目录；train.py 和训练页读取这里
BEST_PT = TRAIN_OUT_DIR / "weights" / "best.pt"  # 当前推理默认读取的 best 权重；predict.py 使用
PREDICT_OUT_DIR = RUNS_DIR / "predict_weights" / f"predict_{TRAIN_PREDICT_VERSION}"  # 旧预测权重目录兼容位；当前主流程基本未直接使用
PREDICT_IMG_DIR = RUNS_DIR / "predict_images"  # 预测结果图输出目录；predict.py 和系统页使用
TEST_IMAGE_DIR = DATA_PATH / "images" / "test"  # 当前默认推理输入目录；predict.py 直接读取这里
TEST_IMAGE = TEST_IMAGE_DIR  # legacy 兼容别名；legacy_physics_stockout 仍在用

# ========================= legacy 路径 =========================
# 这一组是旧几何法方案遗留路径，当前主流程基本不用，但保留给历史脚本兼容。
STOCKOUT_ROOT = ROOT / "legacy_physics_stockout"  # legacy 几何法根目录
STOCKOUT_IMG_DIR = STOCKOUT_ROOT / "predict_images"  # legacy 预测图目录
CSV_DIR = STOCKOUT_ROOT / "analysis" /f"csv_{TRAIN_PREDICT_VERSION}"  # legacy CSV 输出目录
STOCKOUT_STATS_PATH = CSV_DIR / "analysis_results.csv"  # legacy 统计 CSV 路径
STOCKOUT_SENSITIVITY = 0.8  # legacy 几何法敏感度参数；仅旧逻辑参考

NN_ROOT = STOCKOUT_ROOT  # 仅需要修改根目录路径就可实现切换两种识别方式
# ========================= 分析与看板路径 =========================
# 这一组是当前神经网络主流程真实使用的预测图、分析 CSV、模板和静态资源路径。
# NN_ROOT = RUNS_DIR  # 当前神经网络主流程根目录；与活动模型族绑定
NN_IMG_DIR = NN_ROOT / "predict_images"  # 当前主流程预测结果图目录；Web 图片接口读取它
NN_CSV_DIR = NN_ROOT / "analysis" / f"csv_{TRAIN_PREDICT_VERSION}"  # 当前主流程分析输出目录；predict.py 写入这里
NN_STATS_PATH = NN_CSV_DIR / "analysis_results.csv"  # 当前主流程统计 CSV；看板和评估都依赖它

DASHBOARD_TEMPLATE = ROOT / "web_dashboard" / "templates"  # Flask 模板目录；create_app() 使用
DASHBOARD_STATIC = ROOT / "web_dashboard" / "static"  # Flask 静态资源目录；create_app() 使用
CSV_PATH = NN_STATS_PATH  # 当前看板和服务层默认读取的分析 CSV

# ========================= 业务常量 =========================
# 这一组是检测类别和兼容参数常量。
CLASS_PRODUCT = 0  # 检测类别索引：商品；predict.py / detection_analyzer.py 使用
CLASS_EMPTY = 1  # 检测类别索引：空缺；predict.py / detection_analyzer.py 使用
ROW_GAP_RATIO = 0.04  # 旧行距经验参数；当前主流程基本未直接使用，保留兼容


def normalize_worker_count(requested: int | None = None) -> int:
    """将 worker 数限制在当前机器 CPU 核心数范围内。"""
    value = YOLO_WORKERS if requested is None else int(requested)
    return max(1, min(value, CPU_COUNT))


def validate_model_family() -> None:
    """校验模型族配置是否合法。"""
    if ACTIVE_MODEL_FAMILY not in {"yolo26n", "yolo26x"}:
        expected = "yolo26n, yolo26x"
        raise ValueError(
            f"Unsupported ACTIVE_MODEL_FAMILY: {ACTIVE_MODEL_FAMILY}. Expected one of: {expected}"
        )


def validate_model_selection() -> None:
    """校验模型族与基础模型文件名是否明显冲突。"""
    validate_model_family()
    if LOAD_LAST:
        return

    model_stem = Path(MODEL_NAME).stem.lower()
    family_tag = ACTIVE_MODEL_FAMILY.lower()
    if family_tag.endswith("n") and "26x" in model_stem:
        raise ValueError(f"MODEL_NAME does not match ACTIVE_MODEL_FAMILY: {MODEL_NAME} vs {ACTIVE_MODEL_FAMILY}")
    if family_tag.endswith("x") and "26n" in model_stem:
        raise ValueError(f"MODEL_NAME does not match ACTIVE_MODEL_FAMILY: {MODEL_NAME} vs {ACTIVE_MODEL_FAMILY}")


@lru_cache(maxsize=4)
def resolve_yolo_device(probe_runtime: bool = False) -> str | int | None:
    """解析训练/推理应使用的设备，不再强依赖固定 GPU 编号。"""
    if YOLO_DEVICE:
        stripped = YOLO_DEVICE.strip()
        return int(stripped) if stripped.isdigit() else stripped

    if not probe_runtime:
        return None

    try:
        import torch
    except Exception:  # pragma: no cover - 运行环境可能存在 DLL 或驱动问题
        return "cpu"

    return 0 if torch.cuda.is_available() else "cpu"


def can_enable_half_precision(device: str | int | None) -> bool:
    """根据设备类型判断是否允许启用半精度。"""
    if not PREDICT_HALF:
        return False
    if device is None:
        return False
    normalized = str(device).strip().lower()
    return normalized not in {"cpu", "mps"}


def ensure_runtime_dirs() -> None:
    """创建运行期必需存在的目录。"""
    runtime_dirs = (
        STOCKOUT_IMG_DIR,
        CSV_DIR,
        NN_IMG_DIR,
        NN_CSV_DIR,
    )
    for path in runtime_dirs:
        path.mkdir(parents=True, exist_ok=True)


def validate_required_paths() -> None:
    """兼容旧调用：按训练阶段校验关键输入路径。"""
    validate_training_paths()


def validate_source_dirs() -> None:
    """校验源码静态目录是否存在。"""
    if not DASHBOARD_TEMPLATE.exists():
        raise FileNotFoundError(f"Dashboard template directory not found: {DASHBOARD_TEMPLATE}")
    if not DASHBOARD_STATIC.exists():
        raise FileNotFoundError(f"Dashboard static directory not found: {DASHBOARD_STATIC}")


def validate_training_paths() -> None:
    """校验训练阶段依赖的关键输入路径。"""
    validate_model_selection()
    required_paths = (
        (DATA_PATH, "Dataset path not found"),
        (YAML_PATH, "YAML config not found"),
        (MODEL_PATH, "Training init weight not found"),
    )
    for path, message in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"{message}: {path}")


def validate_prediction_paths() -> None:
    """校验推理阶段依赖的关键输入路径。"""
    validate_model_family()
    required_paths = (
        (DATA_PATH, "Dataset path not found"),
        (TEST_IMAGE_DIR, "Prediction input directory not found"),
        (BEST_PT, "Prediction weight not found"),
    )
    for path, message in required_paths:
        if not path.exists():
            raise FileNotFoundError(f"{message}: {path}")


def validate_dashboard_paths() -> None:
    """校验 Web 看板依赖的关键路径。"""
    validate_model_family()
    validate_source_dirs()


def get_training_yaml_path() -> Path:
    """返回训练阶段应使用的 YAML 路径，不直接改写源码配置文件。"""
    with open(YAML_PATH, "r", encoding="utf-8") as file:
        cfg = yaml.safe_load(file) or {}

    raw_yaml_path = str(cfg.get("path", "")).strip()
    if raw_yaml_path:
        yaml_data_path = Path(raw_yaml_path)
        if not yaml_data_path.is_absolute():
            yaml_data_path = (YAML_PATH.parent / yaml_data_path).resolve()
        else:
            yaml_data_path = yaml_data_path.resolve()

        if yaml_data_path == DATA_PATH.resolve():
            return YAML_PATH

    normalized_data_path = str(DATA_PATH).replace("\\", "/")
    if cfg.get("path") == normalized_data_path:
        return YAML_PATH

    cfg["path"] = normalized_data_path
    RUNTIME_YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RUNTIME_YAML_PATH, "w", encoding="utf-8") as file:
        yaml.dump(cfg, file, allow_unicode=True, sort_keys=False)
    return RUNTIME_YAML_PATH


def runtime_snapshot() -> dict:
    """返回当前运行配置快照，便于 Web 和部署层展示。"""
    configured_device = resolve_yolo_device(probe_runtime=False)
    return {
        "timezone": BEIJING_TZ_NAME,

        # 模型与数据
        "active_model_family": ACTIVE_MODEL_FAMILY,
        "model_name": MODEL_NAME,
        "load_last": LOAD_LAST,
        "base_version": BASE_VERSION,
        "train_predict_version": TRAIN_PREDICT_VERSION,
        "yaml_path": str(YAML_PATH),
        "data_path": str(DATA_PATH),

        # 训练参数
        "train_imgsz": TRAIN_IMGSZ,
        "train_epochs": TRAIN_EPOCHS,
        "train_batch": TRAIN_BATCH,
        "train_patience": TRAIN_PATIENCE,

        # 推理参数
        "configured_device": str(configured_device) if configured_device is not None else "auto",
        "runtime_device": "unknown",
        "runtime_device_probed": False,
        "yolo_workers": normalize_worker_count(),
        "predict_imgsz": PREDICT_IMGSZ,
        "predict_half_config": PREDICT_HALF,
        "predict_half_active": can_enable_half_precision(configured_device),
        "predict_save_images": PREDICT_SAVE_IMAGES,

        # 看板参数
        "dashboard_host": DASHBOARD_HOST,
        "dashboard_port": DASHBOARD_PORT,
        "dashboard_record_limit": DASHBOARD_RECORD_LIMIT,

        # 派生路径与分析输出
        "runs_dir": str(RUNS_DIR),
        "model_path": str(MODEL_PATH),
        "best_pt": str(BEST_PT),
        "csv_path": str(CSV_PATH),
        "row_count_cap": ROW_COUNT_CAP if ROW_COUNT_CAP > 0 else "dynamic",
    }


def init_project(stage: str = "train") -> None:
    """显式初始化项目环境：创建目录并按场景校验路径。"""
    ensure_runtime_dirs()
    if not SKIP_CONFIG_VALIDATION:
        validators = {
            "train": (validate_training_paths,),
            "predict": (validate_prediction_paths,),
            "dashboard": (validate_dashboard_paths,),
            "all": (
                validate_source_dirs,
                validate_training_paths,
                validate_prediction_paths,
                validate_dashboard_paths,
            ),
        }
        if stage not in validators:
            raise ValueError(f"Unsupported init stage: {stage}")
        for validator in validators[stage]:
            validator()
