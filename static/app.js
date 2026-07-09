const activeLoaders = new Map();

function formatElapsed(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function resolveIndicator(trigger) {
  const selector = trigger.getAttribute("hx-indicator");
  if (selector) return document.querySelector(selector);
  return trigger.querySelector("[data-loading-status]");
}

function startLoader(indicator) {
  if (!indicator || !indicator.matches("[data-loading-status]")) return;
  stopLoader(indicator);

  const stages = indicator.dataset.stages.split("|").map((stage) => stage.trim()).filter(Boolean);
  const stageEl = indicator.querySelector("[data-stage]");
  const elapsedEl = indicator.querySelector("[data-elapsed]");
  const startedAt = Date.now();

  function render() {
    const elapsedSeconds = Math.floor((Date.now() - startedAt) / 1000);
    const stageIndex = Math.min(Math.floor(elapsedSeconds / 5), stages.length - 1);
    if (stageEl) stageEl.textContent = stages[stageIndex] || "Procesando…";
    if (elapsedEl) elapsedEl.textContent = formatElapsed(elapsedSeconds);
  }

  render();
  const intervalId = window.setInterval(render, 250);
  activeLoaders.set(indicator, intervalId);
}

function stopLoader(indicator) {
  const intervalId = activeLoaders.get(indicator);
  if (!intervalId) return;
  window.clearInterval(intervalId);
  activeLoaders.delete(indicator);
}

function updateOrderLabels(container) {
  container.querySelectorAll(".order-label").forEach((label, index) => {
    label.textContent = String(index + 1);
  });
}

function itemAfterPointer(container, y) {
  const items = [...container.querySelectorAll(".sortable-item:not(.dragging)")];
  return items.reduce(
    (closest, item) => {
      const box = item.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      if (offset < 0 && offset > closest.offset) return { offset, item };
      return closest;
    },
    { offset: Number.NEGATIVE_INFINITY, item: null },
  ).item;
}

function setupSortable(container) {
  if (container.dataset.sortableReady === "true") return;
  container.dataset.sortableReady = "true";

  container.addEventListener("dragstart", (event) => {
    const item = event.target.closest(".sortable-item");
    if (!item) return;
    item.classList.add("dragging");
    event.dataTransfer.effectAllowed = "move";
  });

  container.addEventListener("dragend", (event) => {
    const item = event.target.closest(".sortable-item");
    if (item) item.classList.remove("dragging");
    updateOrderLabels(container);
  });

  container.addEventListener("dragover", (event) => {
    event.preventDefault();
    const dragging = container.querySelector(".dragging");
    if (!dragging) return;
    const after = itemAfterPointer(container, event.clientY);
    if (after) container.insertBefore(dragging, after);
    else container.appendChild(dragging);
    updateOrderLabels(container);
  });
}

function setupSortables(root = document) {
  root.querySelectorAll("[data-sortable]").forEach(setupSortable);
}

document.body.addEventListener("htmx:beforeRequest", (event) => {
  startLoader(resolveIndicator(event.detail.elt));
});

document.body.addEventListener("htmx:afterRequest", (event) => {
  stopLoader(resolveIndicator(event.detail.elt));
});

document.body.addEventListener("htmx:sendError", (event) => {
  stopLoader(resolveIndicator(event.detail.elt));
});

document.body.addEventListener("htmx:responseError", (event) => {
  stopLoader(resolveIndicator(event.detail.elt));
});

document.body.addEventListener("htmx:afterSwap", (event) => {
  setupSortables(event.target);
});

document.addEventListener("DOMContentLoaded", () => setupSortables());
