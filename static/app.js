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
