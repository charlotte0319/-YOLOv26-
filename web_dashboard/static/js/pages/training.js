/*
作用：渲染训练报告页，展示模型指标、核心图表和训练/验证样例。
实现方式：从训练页接口获取指标与图像分组，并通过统一弹窗查看大图。
调用方式：由 app.js 在 training 页面调用 loadTrainingPage()。
*/

import { fetchTrainingPage } from "../api.js";
import { openModal } from "../modal.js";
import { buildAssetModalItems } from "../modal_items.js";
import { createOverviewCards, renderAssetGallery, renderGridState } from "../renderers.js";
import { state } from "../state.js";
import { escapeHtml, formatDecimal } from "../utils.js";

const el = {
  trainingMetricsGrid: document.getElementById("training-metrics-grid"),
  trainingStatusGrid: document.getElementById("training-status-grid"),
  trainingHeroTitle: document.getElementById("training-hero-title"),
  trainingHeroDesc: document.getElementById("training-hero-desc"),
  trainingHeroChips: document.getElementById("training-hero-chips"),
  trainingReportHighlights: document.getElementById("training-report-highlights"),
  trainingCoreAssets: document.getElementById("training-core-assets"),
  trainingConfusionAssets: document.getElementById("training-confusion-assets"),
  trainingValAssets: document.getElementById("training-val-assets"),
  trainingTrainAssets: document.getElementById("training-train-assets"),
};

const assetGroups = new Map();

function bindAssetGallery(container, key) {
  container?.addEventListener("click", (event) => {
    const card = event.target.closest("[data-asset-index]");
    if (!card) {
      return;
    }
    const index = Number(card.dataset.assetIndex || 0);
    const group = assetGroups.get(key);
    if (!group) {
      return;
    }
    openModal(buildAssetModalItems(group.files, group.label), index);
  });
}

function renderTraining(payload) {
  const summary = payload.summary || {};
  const metrics = payload.training_metrics || {};
  const assets = payload.training_assets || {};
  const snapshot = payload.snapshot || {};

  el.trainingHeroTitle.textContent = `${snapshot.active_model_family || "-"} · ${summary.version || "-"}`;
  el.trainingHeroDesc.textContent = "当前页面聚合了模型关键指标、混淆矩阵、曲线图与训练样例，适合做版本核对和结果巡检。";
  el.trainingHeroChips.innerHTML = [
    { label: `版本 ${summary.version || "-"}` },
    { label: `最佳 Epoch ${metrics.best_epoch || 0}` },
    { label: `mAP50-95 ${formatDecimal(metrics.map50_95 || 0, 4)}` },
    { label: `Recall ${formatDecimal(metrics.recall || 0, 4)}` },
  ]
    .map((chip) => `<span class="detail-chip neutral">${escapeHtml(chip.label)}</span>`)
    .join("");

  createOverviewCards(el.trainingMetricsGrid, [
    { title: "最新 Epoch", value: metrics.latest_epoch || 0, helper: "results.csv 最后一轮训练", className: "success" },
    { title: "最佳 Epoch", value: metrics.best_epoch || 0, helper: "按 mAP50-95 最优轮次统计", className: "success" },
    { title: "Precision", value: formatDecimal(metrics.precision || 0, 4), helper: "最新精确率", className: "success" },
    { title: "Recall", value: formatDecimal(metrics.recall || 0, 4), helper: "最新召回率", className: "success" },
    { title: "mAP50", value: formatDecimal(metrics.map50 || 0, 4), helper: "IoU=0.50 指标", className: "warning" },
    { title: "mAP50-95", value: formatDecimal(metrics.map50_95 || 0, 4), helper: "当前模型综合主指标", className: "warning" },
    { title: "F1", value: formatDecimal(metrics.f1 || 0, 4), helper: "由 Precision 与 Recall 计算", className: "warning" },
    { title: "Val Box Loss", value: formatDecimal(metrics.val_box_loss || 0, 4), helper: "验证集框损失", className: "danger" },
  ]);

  createOverviewCards(el.trainingStatusGrid, [
    { title: "活动模型", value: snapshot.active_model_family || "-", helper: "当前运行使用的模型分支", className: "success" },
    { title: "活动版本", value: summary.version || "-", helper: "当前展示的数据版本", className: "warning" },
  ]);

  el.trainingReportHighlights.innerHTML = (payload.training_report?.highlights || []).length
    ? payload.training_report.highlights.map((item) => `<div class="text-item">${escapeHtml(item)}</div>`).join("")
    : '<div class="empty-row">当前没有可展示的运行概览</div>';

  assetGroups.set("core", { files: assets.core_assets || [], label: "核心图表" });
  assetGroups.set("metric", { files: assets.metric_assets || [], label: "指标图表" });
  assetGroups.set("val", { files: assets.validation_samples || [], label: "验证样本" });
  assetGroups.set("train", { files: assets.training_samples || [], label: "训练样本" });

  renderAssetGallery(el.trainingCoreAssets, assets.core_assets || [], "核心图表");
  renderAssetGallery(el.trainingConfusionAssets, assets.metric_assets || [], "指标图表");
  renderAssetGallery(el.trainingValAssets, assets.validation_samples || [], "验证样本");
  renderAssetGallery(el.trainingTrainAssets, assets.training_samples || [], "训练样本");

  if (!metrics.exists && !(assets.core_assets || []).length) {
    renderGridState(el.trainingCoreAssets, "当前未发现训练结果，请先完成训练输出。");
  }
}

export function initTrainingPage() {
  bindAssetGallery(el.trainingCoreAssets, "core");
  bindAssetGallery(el.trainingConfusionAssets, "metric");
  bindAssetGallery(el.trainingValAssets, "val");
  bindAssetGallery(el.trainingTrainAssets, "train");
}

export async function loadTrainingPage() {
  const payload = await fetchTrainingPage();
  state.chrome.summary = payload.summary || null;
  state.chrome.snapshot = payload.snapshot || null;
  state.training.payload = payload;
  renderTraining(payload);
  return payload;
}
