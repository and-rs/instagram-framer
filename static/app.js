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

async function copyCaption(button) {
  const result = button.closest("[data-caption-result]") || button.parentElement?.parentElement;
  const caption = result?.querySelector("[data-caption-text]")?.textContent?.trim();
  if (!caption) return;

  try {
    await navigator.clipboard.writeText(caption);
    const originalLabel = button.textContent;
    button.textContent = "Copiado";
    window.setTimeout(() => { button.textContent = originalLabel; }, 1600);
  } catch {
    button.textContent = "No se pudo copiar";
  }
}

document.body.addEventListener("click", (event) => {
  const button = event.target.closest("[data-copy-caption]");
  if (button) copyCaption(button);
});

const imageInput = document.querySelector("[data-artwork-images]");
const referencePicker = document.querySelector("[data-reference-picker]");
const referenceOptions = document.querySelector("[data-reference-options]");
const referenceEmpty = document.querySelector("[data-reference-empty]");
const collectionNameInput = document.querySelector("[data-collection-name]");
const collectionDescriptionInput = document.querySelector("[data-collection-description]");

function updateCollectionDescriptionRequirement() {
  if (!collectionNameInput || !collectionDescriptionInput) return;
  collectionDescriptionInput.required = !collectionNameInput.value.trim();
}

function renderReferenceOptions() {
  if (!imageInput || !referencePicker || !referenceOptions) return;
  referenceOptions.replaceChildren();
  const files = Array.from(imageInput.files || []);
  if (referenceEmpty) referenceEmpty.hidden = files.length > 0;

  files.forEach((file, index) => {
    const label = document.createElement("label");
    label.className = "cursor-pointer rounded-md border border-slate-200 p-2 text-sm hover:border-slate-400";
    const radio = document.createElement("input");
    radio.type = "radio";
    radio.name = "reference_index";
    radio.value = String(index + 1);
    radio.required = true;
    radio.checked = index === 0;
    const image = document.createElement("img");
    image.className = "mt-2 w-full rounded";
    image.alt = `Referencia ${index + 1}`;
    image.src = URL.createObjectURL(file);
    const caption = document.createElement("span");
    caption.className = "ml-2";
    caption.textContent = `Usar imagen ${index + 1}`;
    label.append(radio, caption, image);
    referenceOptions.append(label);
  });
}

imageInput?.addEventListener("change", renderReferenceOptions);
collectionNameInput?.addEventListener("input", updateCollectionDescriptionRequirement);
window.addEventListener("pageshow", renderReferenceOptions);
updateCollectionDescriptionRequirement();
