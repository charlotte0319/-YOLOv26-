/*
作用：封装前端对 Flask API 的请求。
实现方式：统一处理查询参数拼接、错误抛出和按页面拉取数据。
调用方式：由 app.js 和 pages/*.js 调用 fetchDashboardPage 等函数。
*/

import { state } from "./state.js";

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }
    url.searchParams.set(key, String(value));
  });

  const response = await fetch(url.toString(), { cache: "no-store" });
  if (!response.ok) {
    let detail = `${response.status}`;
    try {
      const payload = await response.json();
      detail = payload?.message || payload?.error || detail;
    } catch (_error) {
      // ignore
    }
    throw new Error(detail);
  }
  return response.json();
}

export function fetchDashboardPage() {
  return apiGet("/api/dashboard", {
    search: state.dashboard.search,
    risk: state.dashboard.risk,
    mid: state.thresholds.mid,
    high: state.thresholds.high,
  });
}

export function fetchRecordsPage() {
  return apiGet("/api/records", {
    page: state.records.page,
    per_page: state.records.perPage,
    search: state.records.search,
    risk: state.records.risk,
    sort: state.records.sort,
    dir: state.records.dir,
    mid: state.thresholds.mid,
    high: state.thresholds.high,
  });
}

export function fetchTrainingPage() {
  return apiGet("/api/training");
}

export function fetchCasesPage() {
  return apiGet("/api/cases", {
    mid: state.thresholds.mid,
    high: state.thresholds.high,
  });
}

export function fetchSystemPage() {
  return apiGet("/api/system");
}

export function fetchHealth() {
  return apiGet("/healthz");
}
