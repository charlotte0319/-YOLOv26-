/*
作用：渲染总览页的概览卡、检测表和单图详情。
实现方式：按当前搜索与风险条件请求总览接口，并将选中记录同步到右侧详情区和弹窗。
调用方式：由 app.js 在 dashboard 页面初始化并调用 loadDashboardPage()。
*/

import { fetchDashboardPage } from "../api.js";
import { openModal } from "../modal.js";
import { buildRecordModalItems } from "../modal_items.js";
import { createOverviewCards, renderTableState } from "../renderers.js";
import { state } from "../state.js";
import { debounce, escapeHtml, formatDateTime, formatPercent, getDisplayName, getRecordAssetFile, toInt } from "../utils.js";

const el = {
  overviewGrid: document.getElementById("overview-grid"),
  dashboardSearch: document.getElementById("dashboard-search"),
  dashboardFilter: document.getElementById("dashboard-filter"),
  dashboardCounter: document.getElementById("dashboard-counter"),
  dashboardRecordsBody: document.getElementById("dashboard-records-body"),
  dashboardStatusPanel: document.getElementById("dashboard-status-panel"),
  dashboardDetailPanel: document.getElementById("dashboard-detail-panel"),
  dashboardDetailTitle: document.getElementById("dashboard-detail-title"),
  dashboardDetailSubtitle: document.getElementById("dashboard-detail-subtitle"),
  dashboardDetailRiskChip: document.getElementById("dashboard-detail-risk-chip"),
  dashboardDetailTimeChip: document.getElementById("dashboard-detail-time-chip"),
  dashboardPreviewTrigger: document.getElementById("dashboard-preview-trigger"),
  dashboardPreviewPlaceholder: document.getElementById("dashboard-preview-placeholder"),
  dashboardPreviewImage: document.getElementById("dashboard-preview-image"),
  dashboardOpenModal: document.getElementById("dashboard-open-modal"),
  dashboardStatProduct: document.getElementById("dashboard-stat-product"),
  dashboardStatEmpty: document.getElementById("dashboard-stat-empty"),
  dashboardStatRatio: document.getElementById("dashboard-stat-ratio"),
  dashboardStatRows: document.getElementById("dashboard-stat-rows"),
  dashboardFileLabel: document.getElementById("dashboard-file-label"),
  dashboardRiskLabel: document.getElementById("dashboard-risk-label"),
  dashboardTimeLabel: document.getElementById("dashboard-time-label"),
  dashboardRowSummary: document.getElementById("dashboard-row-summary"),
  dashboardRowBreakdown: document.getElementById("dashboard-row-breakdown"),
};

let reloadPage = async () => {};
let lastPayload = null;

function syncRiskFilterLabels() {
  if (!el.dashboardFilter) {
    return;
  }
  const allOption = el.dashboardFilter.querySelector('option[value="all"]');
  const highOption = el.dashboardFilter.querySelector('option[value="high"]');
  const midOption = el.dashboardFilter.querySelector('option[value="mid"]');
  const lowOption = el.dashboardFilter.querySelector('option[value="ok"]');
  if (allOption) {
    allOption.textContent = "全部风险";
  }
  if (highOption) {
    highOption.textContent = `高风险 (>= ${state.thresholds.high}%)`;
  }
  if (midOption) {
    midOption.textContent = `中风险 (${state.thresholds.mid}% - ${state.thresholds.high}%)`;
  }
  if (lowOption) {
    lowOption.textContent = `低风险 (< ${state.thresholds.mid}%)`;
  }
}

function getRowColor(rowRatio) {
  if (rowRatio > 0.3) {
    return { bar: "#c05d3c" };
  }
  if (rowRatio > 0.1) {
    return { bar: "#d39a3a" };
  }
  return { bar: "#238364" };
}

function getRowLevel(rowRatio) {
  if (rowRatio > 0.3) {
    return { label: "紧张", className: "high" };
  }
  if (rowRatio > 0.1) {
    return { label: "关注", className: "mid" };
  }
  return { label: "稳定", className: "low" };
}

function syncDashboardPanelHeights() {
  const leftPanel = el.dashboardStatusPanel;
  const rightPanel = el.dashboardDetailPanel;
  if (!leftPanel || !rightPanel) {
    return;
  }
  if (window.innerWidth <= 1260) {
    leftPanel.style.height = "";
    return;
  }
  rightPanel.style.height = "auto";
  leftPanel.style.height = `${rightPanel.offsetHeight}px`;
}

function renderDashboardCards(payload) {
  const summary = payload.summary || {};
  createOverviewCards(el.overviewGrid, [
    { title: "检测图片数", value: summary.image_count || 0, helper: "当前预测 CSV 中的样本数量", className: "success" },
    { title: "商品总数", value: summary.total_product || 0, helper: "累计检测到的商品目标数", className: "success" },
    { title: "空缺总数", value: summary.total_empty || 0, helper: "累计检测到的空缺目标数", className: "danger" },
    { title: "整体空缺率", value: formatPercent(summary.empty_ratio || 0), helper: "按全部目标汇总得到的空缺占比", className: (summary.empty_ratio || 0) > 0.3 ? "danger" : "warning" },
    { title: "最高行数", value: summary.max_rows_detected || 0, helper: "批次内观测到的最大货架层数", className: "warning" },
    { title: "高风险图片", value: payload.high_risk_count || 0, helper: `按当前阈值 >= ${state.thresholds.high}% 统计`, className: "danger" },
  ]);
}

function renderDashboardDetail(record) {
  if (!record) {
    el.dashboardDetailTitle.textContent = "-";
    el.dashboardDetailSubtitle.textContent = "请选择左侧记录查看当前检测状态。";
    el.dashboardDetailRiskChip.textContent = "风险：-";
    el.dashboardDetailRiskChip.className = "detail-chip";
    el.dashboardDetailTimeChip.textContent = "时间：-";
    el.dashboardPreviewPlaceholder.textContent = "请选择左侧记录";
    el.dashboardPreviewPlaceholder.classList.remove("hidden");
    el.dashboardPreviewImage.style.display = "none";
    el.dashboardPreviewImage.removeAttribute("src");
    el.dashboardStatProduct.textContent = "-";
    el.dashboardStatEmpty.textContent = "-";
    el.dashboardStatRatio.textContent = "-";
    el.dashboardStatRows.textContent = "-";
    el.dashboardFileLabel.textContent = "-";
    el.dashboardRiskLabel.textContent = "-";
    el.dashboardTimeLabel.textContent = "-";
    el.dashboardRowSummary.textContent = "-";
    el.dashboardRowBreakdown.innerHTML = '<div class="empty-row">当前没有可展示的行级数据</div>';
    syncDashboardPanelHeights();
    return;
  }

  const rows = Array.isArray(record.row_entries) ? record.row_entries : [];
  const maxEmpty = Math.max(...rows.map((item) => item.empty_count), 1);

  el.dashboardDetailTitle.textContent = getDisplayName(record.file);
  el.dashboardDetailSubtitle.textContent = `当前图片共检测到 ${toInt(record.product_count, 0)} 个商品目标，空缺 ${toInt(record.empty_count, 0)} 个。`;
  el.dashboardDetailRiskChip.textContent = `风险：${record.risk_label || "-"}`;
  el.dashboardDetailRiskChip.className = `detail-chip ${record.risk_class || "neutral"}`;
  el.dashboardDetailTimeChip.textContent = `时间：${formatDateTime(record.timestamp)}`;
  el.dashboardStatProduct.textContent = String(toInt(record.product_count, 0));
  el.dashboardStatEmpty.textContent = String(toInt(record.empty_count, 0));
  el.dashboardStatRatio.textContent = formatPercent(record.empty_ratio || 0);
  el.dashboardStatRows.textContent = `${toInt(record.actual_rows, rows.length)} 行`;
  el.dashboardFileLabel.textContent = record.file || "-";
  el.dashboardRiskLabel.textContent = record.risk_label || "-";
  el.dashboardTimeLabel.textContent = formatDateTime(record.timestamp);
  el.dashboardRowSummary.textContent = `共 ${rows.length} 行，空缺 ${toInt(record.empty_count, 0)} 个`;

  el.dashboardPreviewPlaceholder.textContent = "正在加载预览图...";
  el.dashboardPreviewPlaceholder.classList.remove("hidden");
  el.dashboardPreviewImage.style.display = "none";
  el.dashboardPreviewImage.src = `/api/image/${encodeURIComponent(getRecordAssetFile(record))}`;
  el.dashboardPreviewImage.onload = () => {
    el.dashboardPreviewPlaceholder.classList.add("hidden");
    el.dashboardPreviewImage.style.display = "block";
    syncDashboardPanelHeights();
  };
  el.dashboardPreviewImage.onerror = () => {
    el.dashboardPreviewPlaceholder.textContent = "未找到预测结果图，请先执行 predict.py 生成。";
    el.dashboardPreviewPlaceholder.classList.remove("hidden");
    el.dashboardPreviewImage.style.display = "none";
    syncDashboardPanelHeights();
  };

  el.dashboardRowBreakdown.innerHTML = rows
    .map((item) => {
      const width = item.empty_count > 0 ? Math.max(Math.round((item.empty_count / maxEmpty) * 100), 8) : 0;
      const color = getRowColor(item.empty_ratio || 0);
      const level = getRowLevel(item.empty_ratio || 0);
      return `
        <div class="row-breakdown-item">
          <div class="row-breakdown-line">
            <div class="row-breakdown-head">
              <label>第 ${item.row_no} 行</label>
              <span class="row-breakdown-inline">商品 ${item.product_count}</span>
              <span class="row-breakdown-inline">空缺 ${item.empty_count}</span>
            </div>
            <div class="row-progress compact">
              <div class="row-progress-bar" style="width:${width}%; background:${color.bar};"></div>
            </div>
          </div>
          <div class="row-breakdown-side">
            <span class="row-state-pill ${level.className}">${level.label}</span>
            <strong>${formatPercent(item.empty_ratio || 0)}</strong>
          </div>
        </div>
      `;
    })
    .join("");

  syncDashboardPanelHeights();
}

function renderDashboardTable(payload) {
  lastPayload = payload;
  const records = Array.isArray(payload.records) ? payload.records : [];
  state.dashboard.records = records;
  const displayedTotal = payload.displayed_total || records.length || 0;
  if (payload.is_truncated) {
    el.dashboardCounter.textContent = `当前仅显示前 ${displayedTotal} / ${payload.filtered_total || 0} 条，原始总数 ${payload.record_total || 0} 条`;
  } else {
    el.dashboardCounter.textContent = `显示 ${payload.filtered_total || 0} / ${payload.record_total || 0} 条`;
  }

  if (!records.length) {
    state.dashboard.selectedFile = "";
    renderTableState(el.dashboardRecordsBody, 5, "当前筛选条件下没有记录");
    renderDashboardDetail(null);
    return;
  }

  if (!state.dashboard.selectedFile || !records.some((record) => record.file === state.dashboard.selectedFile)) {
    state.dashboard.selectedFile = records[0].file;
  }

  el.dashboardRecordsBody.innerHTML = records
    .map(
      (record, index) => `
        <tr class="clickable ${record.file === state.dashboard.selectedFile ? "selected" : ""}" data-dashboard-index="${index}">
          <td>${index + 1}</td>
          <td>
            <div class="file-cell compact">
              <strong title="${escapeHtml(record.file || "")}">${escapeHtml(getDisplayName(record.file))}</strong>
            </div>
          </td>
          <td><span class="risk-badge ${record.risk_class || "low"}">${formatPercent(record.empty_ratio || 0)}</span></td>
          <td>${toInt(record.actual_rows, 0)} 行</td>
          <td>${toInt(record.empty_count, 0)}</td>
        </tr>
      `,
    )
    .join("");

  const selectedRecord = records.find((record) => record.file === state.dashboard.selectedFile) || null;
  renderDashboardDetail(selectedRecord);
}

function renderDashboard(payload) {
  syncRiskFilterLabels();
  renderDashboardCards(payload);
  renderDashboardTable(payload);
  syncDashboardPanelHeights();
}

export function initDashboardPage(reload) {
  reloadPage = reload;
  const triggerReload = debounce(() => {
    reloadPage();
  }, 250);

  el.dashboardSearch?.addEventListener("input", (event) => {
    state.dashboard.search = event.target.value || "";
    triggerReload();
  });

  el.dashboardFilter?.addEventListener("change", (event) => {
    state.dashboard.risk = event.target.value || "all";
    reloadPage();
  });

  el.dashboardRecordsBody?.addEventListener("click", (event) => {
    const row = event.target.closest("tr[data-dashboard-index]");
    if (!row) {
      return;
    }
    const index = toInt(row.dataset.dashboardIndex, 0);
    const target = state.dashboard.records[index];
    if (!target) {
      return;
    }
    state.dashboard.selectedFile = target.file;
    if (lastPayload) {
      renderDashboard(lastPayload);
    }
  });

  const openCurrentModal = () => {
    const records = state.dashboard.records || [];
    const startIndex = Math.max(0, records.findIndex((record) => record.file === state.dashboard.selectedFile));
    openModal(buildRecordModalItems(records), startIndex);
  };

  el.dashboardPreviewTrigger?.addEventListener("click", openCurrentModal);
  el.dashboardOpenModal?.addEventListener("click", openCurrentModal);
  window.addEventListener("resize", syncDashboardPanelHeights);
}

export async function loadDashboardPage() {
  const payload = await fetchDashboardPage();
  state.chrome.summary = payload.summary || null;
  state.chrome.snapshot = payload.snapshot || null;
  renderDashboard(payload);
  return payload;
}
