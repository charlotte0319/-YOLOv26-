/*
作用：渲染系统状态页，展示关键路径、运行快照和本地运行检查项。
实现方式：按页面请求系统状态接口，并把路径与运行信息转成信息列表。
调用方式：由 app.js 在 system 页面调用 loadSystemPage()。
*/

import { fetchSystemPage } from "../api.js";
import { createOverviewCards, renderInfoList } from "../renderers.js";
import { state } from "../state.js";
import { formatDateTime } from "../utils.js";

const el = {
  systemCardsGrid: document.getElementById("system-cards-grid"),
  systemPathList: document.getElementById("system-path-list"),
  systemRuntimeList: document.getElementById("system-runtime-list"),
  systemSnapshotBox: document.getElementById("system-snapshot-box"),
};

function renderSystem(payload) {
  const summary = payload.summary || {};
  const system = payload.system || {};
  const snapshot = payload.snapshot || system.snapshot || {};
  const deviceHelper = snapshot.runtime_device_probed
    ? `运行探测：${snapshot.runtime_device || "unknown"}`
    : snapshot.configured_device && snapshot.configured_device !== "auto"
      ? "当前页面未主动探测运行设备，以下信息以手动配置为准"
      : "当前页面未主动探测运行设备，运行时会自动选择可用设备";

  createOverviewCards(el.systemCardsGrid, [
    { title: "预测 CSV", value: system.csv_exists ? "就绪" : "缺失", helper: system.csv_updated_at ? `更新时间：${system.csv_updated_at}` : "尚未生成分析 CSV", className: system.csv_exists ? "success" : "danger" },
    { title: "预测图片目录", value: system.image_dir_exists ? "可访问" : "缺失", helper: `图片数量：${system.predict_image_count || 0}`, className: system.image_dir_exists ? "success" : "danger" },
    { title: "训练结果目录", value: system.train_dir_exists ? "可访问" : "缺失", helper: system.train_updated_at ? `最近更新：${system.train_updated_at}` : "当前目录下未发现训练图像", className: system.train_dir_exists ? "warning" : "danger" },
    { title: "活动模型", value: snapshot.active_model_family || "-", helper: `版本：${snapshot.train_predict_version || "-"}`, className: "success" },
    { title: "批次最大行数", value: summary.max_rows_detected || 0, helper: "当前批次检测到的最大货架层数", className: "warning" },
  ]);

  renderInfoList(el.systemPathList, [
    { label: "模型权重", value: snapshot.model_path || "-", helper: "当前实际加载的模型路径" },
    { label: "数据配置", value: snapshot.yaml_path || "-", helper: "当前 YAML 配置路径" },
    { label: "数据目录", value: snapshot.data_path || "-", helper: "训练与测试数据根目录" },
    { label: "分析 CSV", value: snapshot.csv_path || "-", helper: "管理系统读取的主分析结果文件" },
  ]);

  renderInfoList(el.systemRuntimeList, [
    { label: "设备配置", value: snapshot.configured_device || "auto", helper: deviceHelper, badge: snapshot.runtime_device_probed ? "已探测" : "未探测", badgeClass: snapshot.runtime_device_probed ? "success" : "warning" },
    { label: "预测结果", value: `${system.predict_image_count || 0} 张图片`, helper: "当前预测图片目录中的文件数量", badge: system.image_dir_exists ? "在线" : "缺失", badgeClass: system.image_dir_exists ? "success" : "danger" },
    { label: "分析结果", value: formatDateTime(system.csv_updated_at), helper: "主分析 CSV 最近更新时间", badge: system.csv_exists ? "就绪" : "缺失", badgeClass: system.csv_exists ? "success" : "danger" },
    { label: "训练目录", value: system.train_dir_exists ? "可访问" : "缺失", helper: system.train_updated_at ? `最新训练图更新时间：${system.train_updated_at}` : "当前目录下未发现训练结果图", badge: system.train_dir_exists ? "在线" : "缺失", badgeClass: system.train_dir_exists ? "success" : "danger" },
    { label: "服务入口", value: `${snapshot.dashboard_host || "0.0.0.0"}:${snapshot.dashboard_port || "-"}`, helper: "当前开发服务监听地址" },
  ]);

  el.systemSnapshotBox.textContent = JSON.stringify(snapshot, null, 2);
}

export function initSystemPage() {
  // 当前页无需额外交互绑定。
}

export async function loadSystemPage() {
  const payload = await fetchSystemPage();
  state.chrome.summary = payload.summary || null;
  state.chrome.snapshot = payload.snapshot || payload.system?.snapshot || null;
  state.system.payload = payload;
  renderSystem(payload);
  return payload;
}
