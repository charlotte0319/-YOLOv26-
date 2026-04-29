/*
作用：渲染检测记录页，并提供服务端分页、筛选、排序和阈值配置。
实现方式：将查询条件同步到 state.records，分页参数交给后端处理，前端只负责展示当前页。
调用方式：由 app.js 在 records 页面初始化并调用 loadRecordsPage()。
*/

import { fetchRecordsPage } from "../api.js";
import { openModal } from "../modal.js";
import { buildRecordModalItems } from "../modal_items.js";
import { renderSummaryStrip, renderTableState } from "../renderers.js";
import { loadThresholds, normalizeThresholds, saveThresholds, state } from "../state.js";
import { debounce, escapeHtml, formatDateTime, formatPercent, getDisplayName, toInt } from "../utils.js";

const el = {
  recordsSearch: document.getElementById("records-search"),
  recordsFilter: document.getElementById("records-filter"),
  recordsSort: document.getElementById("records-sort"),
  recordsSortDir: document.getElementById("records-sort-dir"),
  recordsCounter: document.getElementById("records-counter"),
  recordsBody: document.getElementById("records-body"),
  recordsSummaryStrip: document.getElementById("records-summary-strip"),
  riskMidThreshold: document.getElementById("risk-mid-threshold"),
  riskHighThreshold: document.getElementById("risk-high-threshold"),
  riskThresholdApply: document.getElementById("risk-threshold-apply"),
  riskThresholdNote: document.getElementById("risk-threshold-note"),
  recordsPrevPage: document.getElementById("records-prev-page"),
  recordsNextPage: document.getElementById("records-next-page"),
  recordsPageInfo: document.getElementById("records-page-info"),
  recordsPerPage: document.getElementById("records-per-page"),
};

let reloadPage = async () => {};

function syncRiskFilterLabels() {
  [el.recordsFilter].forEach((select) => {
    if (!select) {
      return;
    }
    const allOption = select.querySelector('option[value="all"]');
    const highOption = select.querySelector('option[value="high"]');
    const midOption = select.querySelector('option[value="mid"]');
    const lowOption = select.querySelector('option[value="ok"]');
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
  });
}

function syncThresholdInputs() {
  if (el.riskMidThreshold) {
    el.riskMidThreshold.value = state.thresholds.mid;
  }
  if (el.riskHighThreshold) {
    el.riskHighThreshold.value = state.thresholds.high;
  }
  if (el.riskThresholdNote) {
    el.riskThresholdNote.textContent = `当前规则：低风险 < ${state.thresholds.mid}% ，中风险 ${state.thresholds.mid}% - ${state.thresholds.high}% ，高风险 >= ${state.thresholds.high}%`;
  }
  syncRiskFilterLabels();
}

function renderRows(records, page, perPage) {
  if (!records.length) {
    renderTableState(el.recordsBody, 8, "当前筛选条件下没有记录");
    return;
  }

  el.recordsBody.innerHTML = records
    .map((record, index) => {
      const rowChips = (record.row_entries || [])
        .map((item) => `<span class="row-chip ${item.empty_count > 0 ? "active" : "idle"}" title="第 ${item.row_no} 行空缺 ${item.empty_count} 个">${item.empty_count}</span>`)
        .join("");

      return `
        <tr>
          <td>${(page - 1) * perPage + index + 1}</td>
          <td>
            <div class="file-cell compact">
              <button class="file-open-btn" type="button" data-record-open="${index}" title="${escapeHtml(record.file || "")}">${escapeHtml(getDisplayName(record.file))}</button>
            </div>
          </td>
          <td>${toInt(record.product_count, 0)}</td>
          <td>${toInt(record.empty_count, 0)}</td>
          <td><span class="risk-badge ${record.risk_class || "low"}">${formatPercent(record.empty_ratio || 0)}</span></td>
          <td>${toInt(record.actual_rows, 0)} 行</td>
          <td><div class="row-grid">${rowChips}</div></td>
          <td>${escapeHtml(formatDateTime(record.timestamp))}</td>
        </tr>
      `;
    })
    .join("");
}

function renderPagination(payload) {
  el.recordsPageInfo.textContent = `第 ${payload.page || 1} / ${payload.total_pages || 1} 页`;
  el.recordsPrevPage.disabled = (payload.page || 1) <= 1;
  el.recordsNextPage.disabled = (payload.page || 1) >= (payload.total_pages || 1);
  if (el.recordsPerPage) {
    el.recordsPerPage.value = String(payload.per_page || state.records.perPage);
  }
}

function renderRecords(payload) {
  state.records.items = Array.isArray(payload.records) ? payload.records : [];
  state.records.total = payload.total || 0;
  state.records.totalPages = payload.total_pages || 1;
  state.records.page = payload.page || 1;
  state.records.perPage = payload.per_page || state.records.perPage;
  state.records.stats = payload.stats || {};

  syncThresholdInputs();
  renderSummaryStrip(el.recordsSummaryStrip, [
    { label: "当前匹配", value: `${payload.stats?.current_count || 0} 条`, helper: "筛选后的记录总数", className: "neutral" },
    { label: "高风险", value: `${payload.stats?.high_risk_count || 0} 条`, helper: "按当前阈值统计", className: payload.stats?.high_risk_count ? "danger" : "neutral" },
    { label: "平均空缺率", value: formatPercent(payload.stats?.avg_empty_ratio || 0), helper: "当前筛选结果均值", className: "warning" },
    { label: "最大层数", value: `${payload.stats?.max_rows || 0} 行`, helper: "当前筛选中的最高层数", className: "success" },
  ]);

  const pageStart = payload.total ? (payload.page - 1) * payload.per_page + 1 : 0;
  const pageEnd = Math.min(payload.page * payload.per_page, payload.total || 0);
  el.recordsCounter.textContent = `显示 ${pageStart}-${pageEnd} / ${payload.total || 0} 条`;
  renderRows(state.records.items, payload.page || 1, payload.per_page || state.records.perPage);
  renderPagination(payload);
}

export function initRecordsPage(reload) {
  reloadPage = reload;
  loadThresholds();
  syncThresholdInputs();
  const triggerReload = debounce(() => {
    state.records.page = 1;
    reloadPage();
  }, 250);

  el.recordsSearch?.addEventListener("input", (event) => {
    state.records.search = event.target.value || "";
    triggerReload();
  });
  el.recordsFilter?.addEventListener("change", (event) => {
    state.records.risk = event.target.value || "all";
    state.records.page = 1;
    reloadPage();
  });
  el.recordsSort?.addEventListener("change", (event) => {
    state.records.sort = event.target.value || "default";
    state.records.page = 1;
    reloadPage();
  });
  el.recordsSortDir?.addEventListener("click", () => {
    state.records.dir = state.records.dir === "desc" ? "asc" : "desc";
    el.recordsSortDir.textContent = state.records.dir === "desc" ? "降序" : "升序";
    state.records.page = 1;
    reloadPage();
  });
  el.recordsPerPage?.addEventListener("change", (event) => {
    state.records.perPage = toInt(event.target.value, 40);
    state.records.page = 1;
    reloadPage();
  });
  el.recordsPrevPage?.addEventListener("click", () => {
    state.records.page = Math.max(1, state.records.page - 1);
    reloadPage();
  });
  el.recordsNextPage?.addEventListener("click", () => {
    state.records.page = Math.min(state.records.totalPages || 1, state.records.page + 1);
    reloadPage();
  });
  el.recordsBody?.addEventListener("click", (event) => {
    const button = event.target.closest("[data-record-open]");
    if (!button) {
      return;
    }
    const index = toInt(button.dataset.recordOpen, 0);
    openModal(buildRecordModalItems(state.records.items), index);
  });
  el.riskThresholdApply?.addEventListener("click", () => {
    state.thresholds = normalizeThresholds(el.riskMidThreshold?.value, el.riskHighThreshold?.value);
    saveThresholds();
    syncThresholdInputs();
    state.records.page = 1;
    reloadPage();
  });
}

export async function loadRecordsPage() {
  const payload = await fetchRecordsPage();
  state.chrome.summary = payload.summary || null;
  state.chrome.snapshot = payload.snapshot || null;
  renderRecords(payload);
  return payload;
}
