"""
web_dashboard/data_service.py

作用：
- 作为兼容门面层，保留旧导入路径，避免历史代码和测试直接失效。

实现方式：
- 所有实际实现均已迁移到 `web_dashboard/services/`。
- 本文件只负责统一转发导出，不再承载具体业务逻辑。

调用方式：
- 旧代码仍可使用 `from web_dashboard.data_service import read_csv_data`
- 新代码建议改用 `from web_dashboard.services import read_csv_data`
"""

from web_dashboard.services import (
    DashboardDataError,
    build_cases_page,
    build_dashboard_page,
    build_model_report,
    build_record_analytics,
    build_records_page,
    build_row_entries,
    build_summary,
    build_system_page,
    build_system_status,
    build_training_page,
    classify_risk,
    derive_actual_row_count,
    discover_training_assets,
    enrich_record,
    normalize_thresholds,
    parse_training_results_csv,
    read_csv_data,
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
