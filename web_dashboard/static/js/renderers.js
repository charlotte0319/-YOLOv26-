/*
作用：提供页面公共渲染函数。
实现方式：统一输出概览卡、信息列表、摘要条和空状态，降低页面模块重复代码。
调用方式：由 pages/*.js 导入并调用。
*/

import { escapeHtml } from "./utils.js";

export function createOverviewCards(container, cards) {
  if (!container) {
    return;
  }
  container.innerHTML = cards
    .map(
      (card) => `
        <article class="overview-card ${escapeHtml(card.className || "")}">
          <h3>${escapeHtml(card.title)}</h3>
          <strong>${escapeHtml(card.value)}</strong>
          <p>${escapeHtml(card.helper || "")}</p>
        </article>
      `,
    )
    .join("");
}

export function renderSummaryStrip(container, items) {
  if (!container) {
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <article class="summary-pill ${escapeHtml(item.className || "")}">
          <span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(item.value)}</strong>
          <small>${escapeHtml(item.helper || "")}</small>
        </article>
      `,
    )
    .join("");
}

export function renderInfoList(container, items) {
  if (!container) {
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <article class="info-item">
          <div class="info-item-head">
            <span>${escapeHtml(item.label)}</span>
            ${item.badge ? `<strong class="inline-status ${escapeHtml(item.badgeClass || "")}">${escapeHtml(item.badge)}</strong>` : ""}
          </div>
          <div class="info-item-value">${escapeHtml(item.value)}</div>
          ${item.helper ? `<p>${escapeHtml(item.helper)}</p>` : ""}
        </article>
      `,
    )
    .join("");
}

export function renderTableState(tbody, colSpan, message) {
  if (!tbody) {
    return;
  }
  tbody.innerHTML = `<tr><td colspan="${colSpan}" class="empty-row">${escapeHtml(message)}</td></tr>`;
}

export function renderGridState(container, message) {
  if (!container) {
    return;
  }
  container.innerHTML = `<div class="state-card">${escapeHtml(message)}</div>`;
}

export function renderAssetGallery(container, fileNames, groupLabel) {
  if (!container) {
    return;
  }
  if (!fileNames?.length) {
    renderGridState(container, "当前目录下没有可展示的训练图像");
    return;
  }

  const compact = container.classList.contains("compact") ? "compact" : "";
  container.innerHTML = fileNames
    .map(
      (fileName, index) => `
        <article class="asset-card" data-asset-index="${index}" data-asset-group="${escapeHtml(groupLabel)}">
          <div class="asset-thumb ${compact}">
            <img src="/api/train-asset/${encodeURIComponent(fileName)}" alt="${escapeHtml(fileName)}" loading="lazy" />
          </div>
          <strong title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</strong>
          <span>${escapeHtml(groupLabel)}</span>
        </article>
      `,
    )
    .join("");
}
