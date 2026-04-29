/*
作用：统一管理图片弹窗的打开、关闭和切换行为。
实现方式：保存弹窗数据源和当前位置，并响应按钮、遮罩和键盘事件。
调用方式：先执行 initModal() 绑定事件，再通过 openModal(items, index) 打开。
*/

import { escapeHtml } from "./utils.js";

const modalState = {
  items: [],
  index: 0,
  zoom: 1,
  panX: 0,
  panY: 0,
  dragging: false,
  dragMoved: false,
  dragStartX: 0,
  dragStartY: 0,
  dragOriginX: 0,
  dragOriginY: 0,
};

const el = {
  imageModal: document.getElementById("image-modal"),
  modalPanel: document.querySelector(".modal-panel"),
  modalImageWrap: document.querySelector(".modal-image-wrap"),
  modalSide: document.querySelector(".modal-side"),
  modalClose: document.getElementById("modal-close"),
  modalPrev: document.getElementById("modal-prev"),
  modalNext: document.getElementById("modal-next"),
  modalZoomIn: document.getElementById("modal-zoom-in"),
  modalZoomOut: document.getElementById("modal-zoom-out"),
  modalZoomReset: document.getElementById("modal-zoom-reset"),
  modalZoomValue: document.getElementById("modal-zoom-value"),
  modalImage: document.getElementById("modal-image"),
  modalTitle: document.getElementById("modal-title"),
  modalMeta: document.getElementById("modal-meta"),
  modalSideStats: document.getElementById("modal-side-stats"),
  modalImageFile: document.getElementById("modal-image-file"),
  modalImageOrder: document.getElementById("modal-image-order"),
  modalHeroChips: document.getElementById("modal-hero-chips"),
  modalHeroDesc: document.getElementById("modal-hero-desc"),
};

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function resetZoom() {
  modalState.zoom = 1;
  modalState.panX = 0;
  modalState.panY = 0;
}

function syncImageTransform() {
  if (!el.modalImage) {
    return;
  }
  el.modalImage.style.transform = `translate(${modalState.panX}px, ${modalState.panY}px) scale(${modalState.zoom})`;
  el.modalImage.style.cursor = modalState.zoom > 1 ? (modalState.dragging ? "grabbing" : "grab") : "zoom-in";
  if (el.modalZoomValue) {
    el.modalZoomValue.textContent = `${Math.round(modalState.zoom * 100)}%`;
  }
}

function setZoom(nextZoom) {
  const normalized = Math.max(1, nextZoom);
  if (normalized === 1) {
    modalState.panX = 0;
    modalState.panY = 0;
  }
  modalState.zoom = normalized;
  syncImageTransform();
}

function zoomAtPoint(targetZoom, clientX, clientY) {
  if (!el.modalImage) {
    return;
  }

  const nextZoom = Math.max(1, targetZoom);
  if (nextZoom === 1) {
    resetZoom();
    syncImageTransform();
    return;
  }

  const rect = el.modalImage.getBoundingClientRect();
  const offsetX = clientX - rect.left - rect.width / 2;
  const offsetY = clientY - rect.top - rect.height / 2;
  const scaleRatio = nextZoom / modalState.zoom;

  modalState.panX -= offsetX * (scaleRatio - 1);
  modalState.panY -= offsetY * (scaleRatio - 1);
  modalState.zoom = nextZoom;
  syncImageTransform();
}

function renderModal() {
  const item = modalState.items[modalState.index];
  if (!item) {
    closeModal();
    return;
  }

  el.modalImage.src = item.src;
  resetZoom();
  el.modalTitle.textContent = item.title || "图片预览";
  el.modalHeroDesc.textContent = item.heroDescription || "-";
  el.modalHeroChips.innerHTML = (item.heroChips || [])
    .map((chip) => `<span class="modal-pill ${escapeHtml(chip.className || "neutral")}">${escapeHtml(chip.label)}</span>`)
    .join("");
  el.modalMeta.innerHTML = (item.meta || [])
    .map(
      (meta) => `
        <div class="modal-meta-item">
          <span>${escapeHtml(meta.label)}</span>
          <strong>${escapeHtml(meta.value)}</strong>
        </div>
      `,
    )
    .join("");
  el.modalSideStats.innerHTML = (item.stats || [])
    .map(
      (stat) => `
        <div class="modal-stat-item">
          <span>${escapeHtml(stat.label)}</span>
          <strong>${escapeHtml(stat.value)}</strong>
        </div>
      `,
    )
    .join("");
  el.modalImageFile.textContent = item.title || "-";
  el.modalImageOrder.textContent = `${modalState.index + 1} / ${modalState.items.length}`;
  el.modalPrev.disabled = modalState.index <= 0;
  el.modalNext.disabled = modalState.index >= modalState.items.length - 1;
  el.modalPanel?.scrollTo({ top: 0, left: 0, behavior: "auto" });
  el.modalImageWrap?.scrollTo({ top: 0, left: 0, behavior: "auto" });
  el.modalSide?.scrollTo({ top: 0, left: 0, behavior: "auto" });
  syncImageTransform();
}

export function openModal(items, startIndex = 0) {
  if (!items?.length) {
    return;
  }
  modalState.items = items;
  modalState.index = Math.max(0, Math.min(startIndex, items.length - 1));
  renderModal();
  el.imageModal.hidden = false;
  document.body.style.overflow = "hidden";
}

export function closeModal() {
  if (!el.imageModal) {
    return;
  }
  el.imageModal.hidden = true;
  document.body.style.overflow = "";
  modalState.dragging = false;
  modalState.dragMoved = false;
  resetZoom();
  syncImageTransform();
}

export function initModal() {
  closeModal();

  el.modalClose?.addEventListener("click", closeModal);
  el.modalPrev?.addEventListener("click", () => {
    modalState.index = Math.max(0, modalState.index - 1);
    renderModal();
  });
  el.modalNext?.addEventListener("click", () => {
    modalState.index = Math.min(modalState.items.length - 1, modalState.index + 1);
    renderModal();
  });
  el.modalZoomIn?.addEventListener("click", () => setZoom(modalState.zoom + 0.25));
  el.modalZoomOut?.addEventListener("click", () => setZoom(modalState.zoom - 0.25));
  el.modalZoomReset?.addEventListener("click", () => setZoom(1));
  el.modalImage?.addEventListener("dragstart", (event) => {
    event.preventDefault();
  });
  el.modalImage?.addEventListener("dblclick", (event) => {
    event.preventDefault();
    modalState.dragMoved = false;
    zoomAtPoint(modalState.zoom + 0.5, event.clientX, event.clientY);
  });
  el.modalImage?.addEventListener("pointerdown", (event) => {
    if (modalState.zoom <= 1 || event.button !== 0) {
      return;
    }
    event.preventDefault();
    modalState.dragging = true;
    modalState.dragMoved = false;
    modalState.dragStartX = event.clientX;
    modalState.dragStartY = event.clientY;
    modalState.dragOriginX = modalState.panX;
    modalState.dragOriginY = modalState.panY;
    el.modalImage.setPointerCapture?.(event.pointerId);
    syncImageTransform();
  });
  el.modalImage?.addEventListener("pointermove", (event) => {
    if (!modalState.dragging || modalState.zoom <= 1 || (event.buttons & 1) !== 1) {
      return;
    }
    event.preventDefault();
    const deltaX = event.clientX - modalState.dragStartX;
    const deltaY = event.clientY - modalState.dragStartY;
    if (Math.abs(deltaX) > 2 || Math.abs(deltaY) > 2) {
      modalState.dragMoved = true;
    }
    modalState.panX = modalState.dragOriginX + deltaX;
    modalState.panY = modalState.dragOriginY + deltaY;
    syncImageTransform();
  });
  el.modalImage?.addEventListener("pointerup", (event) => {
    modalState.dragging = false;
    el.modalImage.releasePointerCapture?.(event.pointerId);
    syncImageTransform();
  });
  el.modalImage?.addEventListener("pointercancel", () => {
    modalState.dragging = false;
    syncImageTransform();
  });
  document.addEventListener("pointerup", () => {
    if (!modalState.dragging) {
      return;
    }
    modalState.dragging = false;
    syncImageTransform();
  });

  el.imageModal?.addEventListener("click", (event) => {
    if (event.target === el.imageModal) {
      closeModal();
    }
  });
  el.modalPanel?.addEventListener("click", (event) => {
    event.stopPropagation();
  });

  document.addEventListener("keydown", (event) => {
    if (el.imageModal?.hidden) {
      return;
    }
    if (event.key === "Escape") {
      closeModal();
      return;
    }
    if ((event.key === "+" || event.key === "=") && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      setZoom(modalState.zoom + 0.25);
      return;
    }
    if (event.key === "-" && !event.ctrlKey && !event.metaKey) {
      event.preventDefault();
      setZoom(modalState.zoom - 0.25);
      return;
    }
    if (event.key === "ArrowLeft" && modalState.index > 0) {
      modalState.index -= 1;
      renderModal();
    }
    if (event.key === "ArrowRight" && modalState.index < modalState.items.length - 1) {
      modalState.index += 1;
      renderModal();
    }
  });
}
