/*
作用：作为管理系统前端总入口，负责公共头部、页面初始化与按页刷新。
实现方式：根据 body[data-page] 选择对应页面模块，只请求当前页面数据，不再一次性拉取整包数据。
调用方式：由 templates/page.html 通过 `<script type="module">` 自动加载。
*/

import { fetchHealth } from "./api.js";
import { initModal } from "./modal.js";
import { renderGridState, renderTableState } from "./renderers.js";
import { loadThresholds, state } from "./state.js";
import { initCasesPage, loadCasesPage } from "./pages/cases.js";
import { initDashboardPage, loadDashboardPage } from "./pages/dashboard.js";
import { initRecordsPage, loadRecordsPage } from "./pages/records.js";
import { initSystemPage, loadSystemPage } from "./pages/system.js";
import { initTrainingPage, loadTrainingPage } from "./pages/training.js";

const pageDescriptions = {
  dashboard: "查看当前批次检测结果、风险概况和单张货架的行级空缺详情。",
  records: "按文件名、空缺率、空缺数和行数查看全部检测记录，并支持服务端分页与弹窗大图。",
  training: "集中展示当前 YOLO 权重的训练指标、结果曲线、混淆矩阵和样本图。",
  cases: "集中展示高空缺、密集货架和高层数样本，用于排查典型场景与异常状态。",
  system: "查看系统运行快照、关键路径状态和本地运行建议。",
};

const el = {
  sidebarDesc: document.getElementById("sidebar-page-desc"),
  headerSubtitle: document.getElementById("header-subtitle"),
  badgeVersion: document.getElementById("badge-version"),
  badgeRefresh: document.getElementById("badge-refresh"),
  refreshButton: document.getElementById("action-refresh"),
  healthButton: document.getElementById("action-health"),
};

const pageRegistry = {
  dashboard: { init: initDashboardPage, load: loadDashboardPage },
  records: { init: initRecordsPage, load: loadRecordsPage },
  training: { init: initTrainingPage, load: loadTrainingPage },
  cases: { init: initCasesPage, load: loadCasesPage },
  system: { init: initSystemPage, load: loadSystemPage },
};

function getPageHandler() {
  return pageRegistry[state.pageKey] || pageRegistry.dashboard;
}

function updateChrome(payload) {
  const summary = payload?.summary || state.chrome.summary || {};
  const snapshot = payload?.snapshot || payload?.system?.snapshot || state.chrome.snapshot || {};
  state.chrome.summary = summary;
  state.chrome.snapshot = snapshot;

  if (el.sidebarDesc) {
    el.sidebarDesc.textContent = pageDescriptions[state.pageKey] || "当前页面正在展示系统相关信息。";
  }
  if (el.headerSubtitle) {
    el.headerSubtitle.textContent = `当前模型：${snapshot.active_model_family || "-"}，版本：${snapshot.train_predict_version || "-"}，预测记录：${summary.image_count || 0} 张`;
  }
  if (el.badgeVersion) {
    el.badgeVersion.textContent = `版本：${summary.version || "-"}`;
  }
  if (el.badgeRefresh) {
    el.badgeRefresh.textContent = `最近刷新：${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
  }
}

function renderPageError(message) {
  if (state.pageKey === "dashboard") {
    renderTableState(document.getElementById("dashboard-records-body"), 5, message);
    return;
  }
  if (state.pageKey === "records") {
    renderTableState(document.getElementById("records-body"), 8, message);
    return;
  }
  if (state.pageKey === "training") {
    renderGridState(document.getElementById("training-metrics-grid"), message);
    return;
  }
  if (state.pageKey === "cases") {
    renderGridState(document.getElementById("cases-metrics-grid"), message);
    return;
  }
  renderGridState(document.getElementById("system-cards-grid"), message);
}

async function runHealthCheck() {
  const payload = await fetchHealth();
  window.alert(payload.status === "ok" ? "系统健康检查通过。" : "系统健康检查未通过。");
}

async function refreshCurrentPage(triggerButton) {
  if (triggerButton) {
    triggerButton.disabled = true;
    triggerButton.textContent = "刷新中...";
  }
  if (el.headerSubtitle) {
    el.headerSubtitle.textContent = "正在加载页面数据...";
  }

  try {
    const payload = await getPageHandler().load();
    updateChrome(payload);
  } catch (error) {
    console.error(error);
    if (el.headerSubtitle) {
      el.headerSubtitle.textContent = `数据加载失败：${error.message}`;
    }
    renderPageError(`数据加载失败：${error.message}`);
  } finally {
    if (triggerButton) {
      triggerButton.disabled = false;
      triggerButton.textContent = "刷新数据";
    }
  }
}

function bindCommonEvents() {
  el.refreshButton?.addEventListener("click", () => refreshCurrentPage(el.refreshButton));
  el.healthButton?.addEventListener("click", async () => {
    try {
      await runHealthCheck();
    } catch (error) {
      window.alert(`健康检查失败：${error.message}`);
    }
  });
}

async function bootstrap() {
  loadThresholds();
  bindCommonEvents();
  initModal();
  const handler = getPageHandler();
  handler.init?.(() => refreshCurrentPage());
  await refreshCurrentPage();
}

bootstrap();
