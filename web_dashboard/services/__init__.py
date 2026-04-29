"""
web_dashboard/services/__init__.py

作用：
- 汇总导出管理系统服务层能力，供 Flask 路由和兼容门面统一引用。

实现方式：
- 将 CSV 读取、记录查询、训练结果、案例分析、系统状态拆分到独立模块。
- 统一由本文件暴露稳定导入入口，避免上层直接耦合到底层实现细节。

调用方式：
- `from web_dashboard.services import build_dashboard_page`
- `from web_dashboard.services import read_csv_data`
"""

from .analytics_service import build_cases_page, build_record_analytics
from .csv_reader import (
    DashboardDataError,
    build_row_entries,
    derive_actual_row_count,
    enrich_record,
    read_csv_data,
)
from .records_service import (
    build_dashboard_page,
    build_records_page,
    build_summary,
    classify_risk,
    normalize_thresholds,
)
from .system_service import build_system_page, build_system_status
from .training_service import (
    build_model_report,
    build_training_page,
    discover_training_assets,
    parse_training_results_csv,
    safe_resolve_asset,
)

__all__ = [
    "DashboardDataError",
    "build_cases_page",
    "build_dashboard_page",
    "build_model_report",
    "build_record_analytics",
    "build_records_page",
    "build_row_entries",
    "build_summary",
    "build_system_page",
    "build_system_status",
    "build_training_page",
    "classify_risk",
    "derive_actual_row_count",
    "discover_training_assets",
    "enrich_record",
    "normalize_thresholds",
    "parse_training_results_csv",
    "read_csv_data",
    "safe_resolve_asset",
]
