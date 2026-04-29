/*
作用：渲染案例分析页，展示代表性高风险、密集货架和多层货架样本。
实现方式：从案例接口获取统计和样本数据，并统一接入图片弹窗。
调用方式：由 app.js 在 cases 页面调用 loadCasesPage()。
*/

import { fetchCasesPage } from "../api.js";
import { openModal } from "../modal.js";
import { buildCaseModalItems } from "../modal_items.js";
import { createOverviewCards, renderGridState } from "../renderers.js";
import { state } from "../state.js";
import { escapeHtml, formatPercent, getDisplayName, getRecordAssetFile, toInt } from "../utils.js";

const el = {
  casesMetricsGrid: document.getElementById("cases-metrics-grid"),
  casesHighEmpty: document.getElementById("cases-high-empty"),
  casesDense: document.getElementById("cases-dense"),
  casesRows: document.getElementById("cases-rows"),
};

const groups = new Map();

function renderCaseGallery(container, cases, groupLabel, key) {
  if (!container) {
    return;
  }
  groups.set(key, { cases, label: groupLabel });
  if (!cases?.length) {
    renderGridState(container, "当前没有可展示的案例");
    return;
  }

  container.innerHTML = cases
    .map(
      (item, index) => `
        <article class="case-card" data-case-index="${index}" data-case-group="${key}">
          <div class="case-thumb">
            <img src="/api/image/${encodeURIComponent(getRecordAssetFile(item))}" alt="${escapeHtml(item.file || "案例图")}" loading="lazy" />
          </div>
          <div class="case-body">
            <strong title="${escapeHtml(item.file || "")}">${escapeHtml(getDisplayName(item.file))}</strong>
            <div class="case-tags">
              <span class="risk-badge ${item.risk_class || "low"}">${escapeHtml(item.risk_label || "风险未知")}</span>
              <span class="mini-badge">${escapeHtml(formatPercent(item.empty_ratio || 0))}</span>
              <span class="mini-badge">${escapeHtml(`${toInt(item.actual_rows, 0)} 行`)}</span>
            </div>
            <p>${escapeHtml(`商品 ${toInt(item.product_count, 0)} 个，空缺 ${toInt(item.empty_count, 0)} 个`)}</p>
          </div>
        </article>
      `,
    )
    .join("");
}

function bindGallery(container) {
  container?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-case-index]");
    if (!card) {
      return;
    }
    const index = Number(card.dataset.caseIndex || 0);
    const group = groups.get(card.dataset.caseGroup || "");
    if (!group) {
      return;
    }
    openModal(buildCaseModalItems(group.cases, group.label), index);
  });
}

function renderCases(payload) {
  const analytics = payload.analytics || {};
  const rowDistribution = analytics.row_distribution || [];
  const dominantRows = rowDistribution.reduce(
    (best, item) => (item.image_count > best.image_count ? item : best),
    { row_count: 0, image_count: 0 },
  );
  const riskDistribution = analytics.risk_distribution || [];
  const highRisk = riskDistribution.find((item) => item.risk_class === "high")?.image_count || 0;
  const midRisk = riskDistribution.find((item) => item.risk_class === "mid")?.image_count || 0;
  const lowRisk = riskDistribution.find((item) => item.risk_class === "low")?.image_count || 0;

  createOverviewCards(el.casesMetricsGrid, [
    { title: "高风险样本", value: highRisk, helper: `按当前阈值 >= ${state.thresholds.high}% 统计`, className: "danger" },
    { title: "中风险样本", value: midRisk, helper: `按当前阈值 ${state.thresholds.mid}% - ${state.thresholds.high}% 统计`, className: "warning" },
    { title: "低风险样本", value: lowRisk, helper: `按当前阈值 < ${state.thresholds.mid}% 统计`, className: "success" },
    { title: "主导层数", value: `${dominantRows.row_count || 0} 层`, helper: `该层数出现 ${dominantRows.image_count || 0} 次`, className: "warning" },
  ]);

  renderCaseGallery(el.casesHighEmpty, analytics.top_empty_cases || [], "高空缺案例", "high-empty");
  renderCaseGallery(el.casesDense, analytics.top_dense_cases || [], "密集货架案例", "dense");
  renderCaseGallery(el.casesRows, analytics.top_row_cases || [], "多层货架案例", "rows");
}

export function initCasesPage() {
  bindGallery(el.casesHighEmpty);
  bindGallery(el.casesDense);
  bindGallery(el.casesRows);
}

export async function loadCasesPage() {
  const payload = await fetchCasesPage();
  state.chrome.summary = payload.summary || null;
  state.chrome.snapshot = payload.snapshot || null;
  state.cases.payload = payload;
  renderCases(payload);
  return payload;
}
