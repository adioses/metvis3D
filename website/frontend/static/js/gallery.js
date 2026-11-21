import {formatDate, openPlayer} from "./player.js";

const settings = JSON.parse(document.querySelector("#website-settings").textContent);
const controls = Object.fromEntries(["date", "cycle", "animation", "scene", "software"].map(field => [field, document.querySelector(`#${field}-filter`)]));
const gallery = document.querySelector("#gallery");
const collectionNav = document.querySelector("#collections");
const selection = {collection: "", date: "", cycle: "", animation: "", scene: "", software: ""};
let videos = [];
let collectionTitles = {};

function setOptions(field, options, allLabel) {
  const control = controls[field];
  control.replaceChildren(new Option(allLabel, ""), ...options.map(option => new Option(option.title, option.value)));
  if (!options.some(option => option.value === selection[field])) selection[field] = "";
  control.value = selection[field];
}

function fieldOptions(entries, field) {
  const unique = [...new Set(entries.map(entry => entry[field]))];
  return unique.map(value => {
    const info = entries.find(entry => entry[field] === value)[`${field}_info`];
    return {value, title: info.title, order: info.order ?? Number.MAX_SAFE_INTEGER};
  }).sort((a, b) => a.order - b.order || a.title.localeCompare(b.title, "es"));
}

function updateGallery() {
  let entries = videos.filter(entry => entry.collection === selection.collection);
  const dates = [...new Set(entries.map(entry => entry.date))].sort().reverse();
  setOptions("date", dates.map(value => ({value, title: formatDate(value)})), "Todas las fechas");
  if (selection.date) entries = entries.filter(entry => entry.date === selection.date);
  const cycles = [...new Set(entries.map(entry => entry.cycle))].sort();
  setOptions("cycle", cycles.map(value => ({value, title: `${value}:00 UTC`})), "Todas las horas");
  document.querySelector("#cycle-group").hidden = cycles.length < 2;
  if (cycles.length < 2) selection.cycle = "";
  if (selection.cycle) entries = entries.filter(entry => entry.cycle === selection.cycle);
  setOptions("animation", fieldOptions(entries, "animation"), "Todas las animaciones");
  if (selection.animation) entries = entries.filter(entry => entry.animation === selection.animation);
  setOptions("scene", fieldOptions(entries, "scene"), "Todas las escenas");
  if (selection.scene) entries = entries.filter(entry => entry.scene === selection.scene);
  const tools = fieldOptions(entries, "software");
  setOptions("software", tools, "Todas las herramientas");
  document.querySelector("#software-group").hidden = tools.length < 2;
  if (tools.length < 2) selection.software = "";
  if (selection.software) entries = entries.filter(entry => entry.software === selection.software);

  entries.sort((a, b) => {
    if (a.reference !== b.reference) return b.reference.localeCompare(a.reference);
    for (const field of ["animation", "scene", "source", "software"]) {
      const order = (a[`${field}_info`].order ?? Number.MAX_SAFE_INTEGER) - (b[`${field}_info`].order ?? Number.MAX_SAFE_INTEGER);
      if (order) return order;
      const titleOrder = a[`${field}_info`].title.localeCompare(b[`${field}_info`].title, "es");
      if (titleOrder) return titleOrder;
    }
    return 0;
  });
  gallery.replaceChildren();
  for (const entry of entries) {
    const fragment = document.querySelector("#video-card-template").content.cloneNode(true);
    const button = fragment.querySelector("button");
    const image = fragment.querySelector(".thumbnail");
    const placeholder = fragment.querySelector(".thumbnail-placeholder");
    button.setAttribute("aria-label", `Reproducir ${entry.animation_info.title}, ${entry.source_info.title}, ${entry.software_info.title}, ${formatDate(entry.date)}, ${entry.cycle}:00 UTC`);
    if (entry.thumbnail_url) {
      image.src = entry.thumbnail_url;
      image.addEventListener("error", () => { image.hidden = true; placeholder.hidden = false; }, {once: true});
    } else { image.hidden = true; placeholder.hidden = false; }
    fragment.querySelector("h3").textContent = entry.animation_info.title;
    fragment.querySelector(".source-label").textContent = entry.source_info.title;
    fragment.querySelector(".software-label").textContent = entry.software_info.title;
    fragment.querySelector(".scene-label").textContent = entry.scene_info.title;
    fragment.querySelector(".reference-label").textContent = `${formatDate(entry.date)} · ${entry.cycle}:00 UTC`;
    const duration = entry.metadata.playback?.duration_seconds;
    if (duration) {
      const label = fragment.querySelector(".duration");
      label.textContent = `${duration.toLocaleString("es-PE", {maximumFractionDigits: 1})} s`;
      label.hidden = false;
    }
    button.addEventListener("click", () => openPlayer(entry));
    gallery.append(fragment);
  }
  const sourceCount = new Set(entries.map(entry => entry.source)).size;
  document.querySelector("#results-title").textContent = `${entries.length} ${entries.length === 1 ? "animación disponible" : "animaciones disponibles"}`;
  document.querySelector("#results-description").textContent = entries.length ? `${sourceCount} ${sourceCount === 1 ? "fuente" : "fuentes"} · ${selection.date ? formatDate(selection.date) : "Todas las fechas"}` : "";
  document.querySelector("#empty-state").hidden = entries.length > 0;
  for (const button of collectionNav.querySelectorAll("button")) button.setAttribute("aria-pressed", String(button.dataset.collection === selection.collection));
}

Object.entries(controls).forEach(([field, control]) => control.addEventListener("change", () => {
  selection[field] = control.value;
  if (field === "date") selection.cycle = "";
  updateGallery();
}));

const themeToggle = document.querySelector("#theme-toggle");
function updateThemeLabel() {
  const label = document.documentElement.dataset.theme === "dark" ? "Tema claro" : "Tema oscuro";
  document.querySelector("#theme-label").textContent = label;
  themeToggle.setAttribute("aria-label", `Cambiar a ${label.toLowerCase()}`);
}
updateThemeLabel();
themeToggle.addEventListener("click", () => {
  document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("metvis3d-theme", document.documentElement.dataset.theme);
  updateThemeLabel();
});

async function loadCatalog() {
  try {
    const response = await fetch(settings.catalog_url, {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `No se pudo leer el catálogo: HTTP ${response.status}.`);
    videos = data.videos;
    collectionTitles = data.collections;
    const available = Object.keys(collectionTitles).filter(collection => videos.some(entry => entry.collection === collection));
    for (const collection of available) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.collection = collection;
      button.textContent = collectionTitles[collection];
      const count = document.createElement("span");
      count.className = "collection-count";
      count.textContent = videos.filter(entry => entry.collection === collection).length;
      button.append(count);
      button.addEventListener("click", () => {
        selection.collection = collection;
        selection.date = videos.find(entry => entry.collection === collection).date;
        selection.cycle = selection.animation = selection.scene = selection.software = "";
        updateGallery();
      });
      collectionNav.append(button);
    }
    collectionNav.hidden = !available.length;
    document.querySelector("#filters-panel").hidden = !available.length;
    selection.collection = available[0] || "";
    selection.date = videos.find(entry => entry.collection === selection.collection)?.date || "";
    updateGallery();
  } catch (error) {
    document.querySelector("#results-title").textContent = "No se pudo cargar la biblioteca";
    const message = document.querySelector("#catalog-error");
    message.textContent = `${error.message} Corrige el problema y vuelve a cargar la página.`;
    message.hidden = false;
    gallery.replaceChildren();
  } finally { document.querySelector("#results-section").setAttribute("aria-busy", "false"); }
}
loadCatalog();
