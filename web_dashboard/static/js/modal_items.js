/*
作用：构建图片弹窗所需的数据结构。
实现方式：将预测记录、案例记录和训练图表统一转换为 modal item。
调用方式：由 pages/*.js 在打开弹窗前调用。
*/

import { formatDateTime, formatPercent, getRecordAssetFile, toInt } from "./utils.js";

function inferAssetMeaning(fileName) {
  const lower = String(fileName).toLowerCase();
  if (lower.includes("confusion_matrix")) {
    return "类别混淆矩阵，用于检查分类错误分布。";
  }
  if (lower.includes("results")) {
    return "训练过程总览图，用于观察收敛趋势。";
  }
  if (lower.includes("curve")) {
    return "精度、召回率与 F1 曲线。";
  }
  if (lower.includes("labels")) {
    return "数据标注分布与样本概览。";
  }
  if (lower.includes("val_batch")) {
    return "验证集预测结果样本图。";
  }
  if (lower.includes("train_batch")) {
    return "训练过程中的样本批次图。";
  }
  return "训练阶段图像产出。";
}

export function buildRecordModalItems(records) {
  return records.map((record) => ({
    src: `/api/image/${encodeURIComponent(getRecordAssetFile(record))}`,
    title: record.file || "预测结果",
    heroDescription: `当前图片检测到 ${toInt(record.product_count, 0)} 个商品、${toInt(record.empty_count, 0)} 个空缺，货架共 ${toInt(record.actual_rows, 0)} 行。`,
    heroChips: [
      { label: record.risk_label || "风险未知", className: record.risk_class || "neutral" },
      { label: formatPercent(record.empty_ratio || 0), className: "neutral" },
      { label: `${toInt(record.actual_rows, 0)} 行`, className: "neutral" },
    ],
    meta: [
      { label: "类型", value: "预测结果图" },
      { label: "原始文件", value: record.file || "-" },
      { label: "检测时间", value: formatDateTime(record.timestamp) },
    ],
    stats: [
      { label: "商品数", value: String(toInt(record.product_count, 0)) },
      { label: "空缺数", value: String(toInt(record.empty_count, 0)) },
      { label: "空缺率", value: formatPercent(record.empty_ratio || 0) },
      { label: "有效层数", value: String(toInt(record.actual_rows, 0)) },
    ],
  }));
}

export function buildCaseModalItems(cases, groupLabel) {
  return cases.map((item) => ({
    src: `/api/image/${encodeURIComponent(getRecordAssetFile(item))}`,
    title: item.file || groupLabel,
    heroDescription: `${groupLabel}用于展示不同货架状态下的代表性样本，便于排查异常分布和观察典型货架状态。`,
    heroChips: [
      { label: item.risk_label || "风险未知", className: item.risk_class || "neutral" },
      { label: formatPercent(item.empty_ratio || 0), className: "neutral" },
      { label: `${toInt(item.actual_rows, 0)} 行`, className: "neutral" },
    ],
    meta: [
      { label: "案例类型", value: groupLabel },
      { label: "原始文件", value: item.file || "-" },
      { label: "检测时间", value: formatDateTime(item.timestamp) },
      { label: "货架层数", value: `${toInt(item.actual_rows, 0)} 行` },
    ],
    stats: [
      { label: "商品数", value: String(toInt(item.product_count, 0)) },
      { label: "空缺数", value: String(toInt(item.empty_count, 0)) },
      { label: "空缺率", value: formatPercent(item.empty_ratio || 0) },
      { label: "使用建议", value: "适合用于查看异常样本和典型场景。" },
    ],
  }));
}

export function buildAssetModalItems(fileNames, groupLabel) {
  return fileNames.map((fileName) => ({
    src: `/api/train-asset/${encodeURIComponent(fileName)}`,
    title: fileName,
    heroDescription: inferAssetMeaning(fileName),
    heroChips: [
      { label: "训练图表", className: "neutral" },
      { label: groupLabel, className: "neutral" },
    ],
    meta: [
      { label: "类型", value: "训练图像" },
      { label: "文件名", value: fileName },
      { label: "来源", value: "当前活动训练输出目录" },
      { label: "分组", value: groupLabel },
    ],
    stats: [
      { label: "用途", value: inferAssetMeaning(fileName) },
      { label: "建议", value: "适合用于模型巡检、版本对比和训练复盘。" },
    ],
  }));
}
