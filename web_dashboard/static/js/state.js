/*
作用：维护前端页面运行状态与风险阈值配置。
实现方式：集中保存页面公共状态，并用 localStorage 持久化风险阈值。
调用方式：由 app.js 和 pages/*.js 导入 state 与阈值工具函数。
*/

const THRESHOLD_STORAGE_KEY = "yolov26-risk-thresholds";

export const state = {
  pageKey: document.body.dataset.page || "dashboard",
  thresholds: { mid: 10, high: 30 },
  chrome: { summary: null, snapshot: null },
  dashboard: {
    search: "",
    risk: "all",
    records: [],
    selectedFile: "",
  },
  records: {
    search: "",
    risk: "all",
    sort: "default",
    dir: "desc",
    page: 1,
    perPage: 40,
    items: [],
    total: 0,
    totalPages: 1,
    stats: null,
  },
  training: {
    payload: null,
  },
  cases: {
    payload: null,
  },
  system: {
    payload: null,
  },
};

export function normalizeThresholds(mid, high) {
  const safeMid = Math.max(0, Math.min(Number(mid) || 10, 99));
  const safeHigh = Math.max(safeMid + 0.1, Math.min(Number(high) || 30, 100));
  return {
    mid: Number(safeMid.toFixed(1)),
    high: Number(safeHigh.toFixed(1)),
  };
}

export function loadThresholds() {
  try {
    const raw = window.localStorage.getItem(THRESHOLD_STORAGE_KEY);
    if (!raw) {
      return state.thresholds;
    }
    const parsed = JSON.parse(raw);
    state.thresholds = normalizeThresholds(parsed?.mid, parsed?.high);
    return state.thresholds;
  } catch (error) {
    console.warn("风险阈值读取失败", error);
    return state.thresholds;
  }
}

export function saveThresholds() {
  window.localStorage.setItem(THRESHOLD_STORAGE_KEY, JSON.stringify(state.thresholds));
}
