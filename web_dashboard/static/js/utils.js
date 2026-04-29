/*
作用：提供前端通用工具函数。
实现方式：集中处理数值转换、格式化、转义和防抖，避免各页面重复实现。
调用方式：由 app.js、modal.js 和 pages/*.js 通过 ES Module 导入。
*/

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function toInt(value, fallback = 0) {
  const parsed = Number.parseInt(Number(value), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function toFloat(value, fallback = 0) {
  const parsed = Number.parseFloat(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function formatPercent(value) {
  return `${(toFloat(value) * 100).toFixed(1)}%`;
}

export function formatDecimal(value, digits = 4) {
  return toFloat(value).toFixed(digits);
}

export function formatDateTime(value) {
  return value ? String(value) : "-";
}

export function getDisplayName(fileName) {
  const raw = String(fileName || "").trim();
  if (!raw) {
    return "-";
  }
  const dotIndex = raw.lastIndexOf(".");
  return dotIndex > 0 ? raw.slice(0, dotIndex) : raw;
}

export function getRecordAssetFile(record) {
  if (!record || typeof record !== "object") {
    return "";
  }
  return String(record.asset_file || record.file || "").trim();
}

export function debounce(fn, delay = 250) {
  let timer = null;
  return (...args) => {
    window.clearTimeout(timer);
    timer = window.setTimeout(() => fn(...args), delay);
  };
}
