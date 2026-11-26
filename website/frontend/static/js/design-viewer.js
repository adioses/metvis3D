import {formatDate, showVideo, clearVideo} from "./inline-player.js";

const settings = JSON.parse(document.querySelector("#website-settings").textContent);
const isEditorial = document.body.classList.contains("design-editorial");
const controls = Object.fromEntries(["date", "cycle", "scene", "software"].map(field => [field, document.querySelector(`#${field}-filter`)]).filter(([, control]) => control));
const collectionNav = document.querySelector("#collections");
const animationNav = document.querySelector("#animations");
const modelNav = document.querySelector("#models");
const versionControl = document.querySelector("#version-filter");
const previewNav = document.querySelector("#video-previews");
const selection = {collection: "", date: "", cycle: "", scene: "", software: "", animation: "", source: "", video: ""};
let videos = [];
let filteredVideos = [];

function fieldOptions(entries, field) {
  return [...new Set(entries.map(entry => entry[field]))].map(value => {
    const info = entries.find(entry => entry[field] === value)[`${field}_info`];
    return {value, title: info.title, description: info.description || "", shortDescription: info.short_description || info.description || "", order: info.order ?? Number.MAX_SAFE_INTEGER};
  }).sort((a, b) => a.order - b.order || a.title.localeCompare(b.title, "es"));
}

function setOptions(field, options, allLabel) {
  // Un filtro retirado de la presentación no debe restringir corridas invisiblemente.
  if (!(field in controls)) {
    selection[field] = "";
    return;
  }
  const control = controls[field];
  control.replaceChildren(new Option(allLabel, ""), ...options.map(option => new Option(option.title, option.value)));
  if (!options.some(option => option.value === selection[field])) selection[field] = "";
  control.value = selection[field];
  control.disabled = options.length === 0;
}

function fitEditorialVideo() {
  const workspace = document.querySelector("#viewer-workspace");
  if (workspace.hidden) return;
  const stage = document.querySelector(".video-stage");
  const tools = document.querySelector(".playback-tools");
  const previews = document.querySelector("#video-previews-section");
  let previewSpace = 0;
  if (!previews.hidden) {
    const previewHeading = previews.querySelector(".previews-heading");
    const previewStyle = getComputedStyle(previews);
    const headingStyle = getComputedStyle(previewHeading);
    // Reservar el encabezado y el inicio de las miniaturas para descubrir otras versiones.
    previewSpace = parseFloat(previewStyle.marginTop) + parseFloat(previewStyle.borderTopWidth)
      + parseFloat(previewStyle.paddingTop) + previewHeading.offsetHeight
      + parseFloat(headingStyle.marginBottom) + 72;
  }
  const videoHeight = Math.max(180, window.innerHeight - stage.getBoundingClientRect().top - window.scrollY - tools.offsetHeight - previewSpace - 16);
  workspace.style.setProperty("--editorial-video-height", `${videoHeight}px`);
  // La altura real contempla también el límite impuesto por la anchura del video 16:9.
  workspace.style.setProperty("--editorial-explorer-height", `${stage.getBoundingClientRect().height}px`);
}

function updatePreviewNavigation() {
  const previous = document.querySelector("#previews-previous");
  const next = document.querySelector("#previews-next");
  previous.disabled = previewNav.scrollLeft <= 1;
  next.disabled = previewNav.scrollLeft + previewNav.clientWidth >= previewNav.scrollWidth - 1;
}

function updateEditorialPreviews() {
  const versions = filteredVideos.filter(entry => entry.animation === selection.animation);
  previewNav.replaceChildren();
  previewNav.scrollLeft = 0;
  for (const entry of versions) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "video-preview";
    button.dataset.video = entry.id;
    button.setAttribute("aria-pressed", String(entry.id === selection.video));
    button.setAttribute("aria-label", `Mostrar ${entry.animation_info.title}, ${entry.source_info.title}, ${entry.scene_info.title}, ${entry.software_info.title}, ${formatDate(entry.date)}, ${entry.cycle}:00 UTC`);
    const picture = document.createElement("span");
    picture.className = "preview-picture";
    const placeholder = document.createElement("span");
    placeholder.className = "preview-placeholder";
    placeholder.textContent = "Sin miniatura disponible";
    placeholder.hidden = Boolean(entry.thumbnail_url);
    if (entry.thumbnail_url) {
      const image = document.createElement("img");
      image.src = entry.thumbnail_url;
      image.alt = "";
      image.loading = "lazy";
      image.decoding = "async";
      image.addEventListener("error", () => { image.hidden = true; placeholder.hidden = false; }, {once: true});
      picture.append(image);
    }
    picture.append(placeholder);
    const information = document.createElement("span");
    information.className = "preview-information";
    const model = document.createElement("strong");
    model.textContent = entry.source_info.title;
    const software = document.createElement("span");
    software.className = "preview-software";
    software.textContent = entry.software_info.title;
    const scene = document.createElement("span");
    scene.textContent = entry.scene_info.title;
    const reference = document.createElement("span");
    reference.className = "preview-reference";
    reference.textContent = `${formatDate(entry.date)} · ${entry.cycle}:00 UTC`;
    information.append(model, software, scene, reference);
    button.append(picture, information);
    button.addEventListener("click", () => {
      selection.video = entry.id;
      updateSelectedVideo();
    });
    previewNav.append(button);
  }
  document.querySelector("#video-previews-section").hidden = versions.length === 0;
  document.querySelector("#preview-count").textContent = `${versions.length} ${versions.length === 1 ? "versión de la animación seleccionada" : "versiones de la animación seleccionada"}`;
  requestAnimationFrame(updatePreviewNavigation);
}

function updateSelectedVideo() {
  const animationVideos = filteredVideos.filter(entry => entry.animation === selection.animation);
  let entry;
  if (isEditorial) {
    // Los previews abarcan todos los modelos; sólo los filtros superiores restringen versiones.
    if (!animationVideos.some(item => item.id === selection.video)) selection.video = animationVideos[0].id;
    entry = animationVideos.find(item => item.id === selection.video);
    selection.source = entry.source;
    for (const button of previewNav.querySelectorAll("button")) button.setAttribute("aria-pressed", String(button.dataset.video === entry.id));
  } else {
    const sources = fieldOptions(animationVideos, "source");
    if (!sources.some(source => source.value === selection.source)) selection.source = sources[0].value;
    modelNav.replaceChildren();
    for (const source of sources) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = source.title;
      button.dataset.source = source.value;
      button.title = source.description || source.title;
      button.setAttribute("aria-pressed", String(source.value === selection.source));
      button.addEventListener("click", () => {
        selection.source = source.value;
        updateSelectedVideo();
        modelNav.querySelector(`[data-source="${CSS.escape(source.value)}"]`).focus();
      });
      modelNav.append(button);
    }

    // El panorámico conserva su selección de modelos y el listado de versiones original.
    const versions = animationVideos.filter(item => item.source === selection.source);
    if (!versions.some(item => item.id === selection.video)) selection.video = versions[0].id;
    versionControl.replaceChildren(...versions.map(item => new Option(`${formatDate(item.date)} · ${item.cycle}:00 UTC · ${item.scene_info.title} · ${item.software_info.title}`, item.id)));
    versionControl.value = selection.video;
    document.querySelector("#version-group").hidden = versions.length < 2;
    entry = versions.find(item => item.id === selection.video);
  }
  showVideo(entry);
  if (isEditorial) requestAnimationFrame(fitEditorialVideo);

  // Los enlaces entre propuestas conservan exactamente el video elegido.
  for (const link of document.querySelectorAll("[data-design-link]")) {
    const url = new URL(link.href);
    url.searchParams.set("video", entry.id);
    link.href = url.href;
  }
}

function updateAnimations() {
  const animations = fieldOptions(filteredVideos, "animation");
  if (!animations.some(animation => animation.value === selection.animation)) selection.animation = animations[0].value;
  animationNav.replaceChildren();
  for (const [index, animation] of animations.entries()) {
    const row = document.createElement("div");
    row.className = "animation-option";
    row.classList.toggle("is-selected", animation.value === selection.animation);
    const button = document.createElement("button");
    button.className = "animation-choice";
    button.type = "button";
    button.dataset.animation = animation.value;
    button.setAttribute("aria-pressed", String(animation.value === selection.animation));
    if (isEditorial) {
      const number = document.createElement("span");
      number.className = "animation-number";
      number.textContent = String(index + 1).padStart(2, "0");
      button.append(number);
    }
    const text = document.createElement("span");
    text.className = "animation-text";
    const title = document.createElement("span");
    title.className = "animation-title";
    title.textContent = animation.title;
    if (isEditorial) text.append(title);
    else button.append(title);
    const descriptionText = isEditorial ? animation.shortDescription : animation.description;
    if (descriptionText) {
      const description = document.createElement("span");
      description.className = "animation-summary";
      description.textContent = descriptionText;
      if (isEditorial) text.append(description);
      else button.append(description);
    }
    if (isEditorial) button.append(text);
    if (!isEditorial) {
      const sources = document.createElement("span");
      sources.className = "animation-sources";
      sources.textContent = fieldOptions(filteredVideos.filter(entry => entry.animation === animation.value), "source").map(source => source.title).join(" · ");
      button.append(sources);
    }
    button.addEventListener("click", () => {
      selection.animation = animation.value;
      if (isEditorial) {
        updateAnimations();
        animationNav.querySelector(`[data-animation="${CSS.escape(animation.value)}"]`).focus({preventScroll: true});
        return;
      }
      for (const item of animationNav.querySelectorAll("button")) item.setAttribute("aria-pressed", String(item.dataset.animation === selection.animation));
      updateSelectedVideo();
    });
    if (isEditorial) {
      row.append(button);
      animationNav.append(row);
    } else animationNav.append(button);
  }
  document.querySelector("#animation-count").textContent = String(animations.length);
  if (isEditorial) updateEditorialPreviews();
  updateSelectedVideo();
}

function updateLibrary() {
  // Colección y filtros meteorológicos delimitan primero los productos disponibles.
  let entries = videos.filter(entry => entry.collection === selection.collection);
  const dates = [...new Set(entries.map(entry => entry.date))].sort().reverse();
  setOptions("date", dates.map(value => ({value, title: formatDate(value)})), "Todas las fechas");
  if (selection.date) entries = entries.filter(entry => entry.date === selection.date);
  const cycles = [...new Set(entries.map(entry => entry.cycle))].sort();
  setOptions("cycle", cycles.map(value => ({value, title: `${value}:00 UTC`})), "Todos los ciclos");
  if (selection.cycle) entries = entries.filter(entry => entry.cycle === selection.cycle);
  setOptions("scene", fieldOptions(entries, "scene"), "Todas las escenas");
  if (selection.scene) entries = entries.filter(entry => entry.scene === selection.scene);
  setOptions("software", fieldOptions(entries, "software"), "Todas las herramientas");
  if (selection.software) entries = entries.filter(entry => entry.software === selection.software);
  filteredVideos = entries;

  const animations = fieldOptions(entries, "animation");
  document.querySelector("#results-description").textContent = `${animations.length} ${animations.length === 1 ? "tipo de animación" : "tipos de animación"} · ${entries.length} ${entries.length === 1 ? "video disponible" : "videos disponibles"}${selection.date ? ` · ${formatDate(selection.date)}` : ""}`;
  document.querySelector("#empty-state").hidden = entries.length > 0;
  document.querySelector("#viewer-workspace").hidden = entries.length === 0;
  document.querySelector("#video-information").hidden = entries.length === 0;
  for (const button of collectionNav.querySelectorAll("button")) button.setAttribute("aria-pressed", String(button.dataset.collection === selection.collection));
  if (!entries.length) {
    clearVideo();
    animationNav.replaceChildren();
    if (isEditorial) {
      previewNav.replaceChildren();
      document.querySelector("#video-previews-section").hidden = true;
    } else modelNav.replaceChildren();
    for (const link of document.querySelectorAll("[data-design-link]")) {
      const url = new URL(link.href);
      url.searchParams.delete("video");
      link.href = url.href;
    }
    return;
  }
  updateAnimations();
}

Object.entries(controls).forEach(([field, control]) => control.addEventListener("change", () => {
  selection[field] = control.value;
  if (field === "date") selection.cycle = "";
  updateLibrary();
}));
if (!isEditorial) {
  versionControl.addEventListener("change", () => {
    selection.video = versionControl.value;
    updateSelectedVideo();
  });
}

if (isEditorial) {
  const sizeChanges = new ResizeObserver(() => requestAnimationFrame(fitEditorialVideo));
  for (const element of document.querySelectorAll(".site-header, .viewer-intro, .editorial-video-heading, .playback-tools, .previews-heading, .demo-banner")) sizeChanges.observe(element);
  const previewSize = new ResizeObserver(() => requestAnimationFrame(updatePreviewNavigation));
  previewSize.observe(previewNav);
  previewNav.addEventListener("scroll", () => requestAnimationFrame(updatePreviewNavigation));
  for (const [selector, direction] of [["#previews-previous", -1], ["#previews-next", 1]]) {
    document.querySelector(selector).addEventListener("click", () => {
      previewNav.scrollBy({left: direction * previewNav.clientWidth, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
    });
  }
  window.addEventListener("resize", () => requestAnimationFrame(fitEditorialVideo));
}

async function loadLibrary() {
  try {
    const response = await fetch(settings.catalog_url, {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `No se pudo leer el catálogo: HTTP ${response.status}.`);
    videos = data.videos;
    if (isEditorial) {
      const animationTexts = JSON.parse(document.querySelector("#editorial-settings").textContent);
      for (const entry of videos) entry.animation_info = {...entry.animation_info, ...animationTexts[entry.animation]};
    }
    // La referencia más reciente y los órdenes del YAML definen la selección inicial.
    videos.sort((a, b) => {
      if (a.reference !== b.reference) return b.reference.localeCompare(a.reference);
      for (const field of ["animation", "scene", "source", "software"]) {
        const order = (a[`${field}_info`].order ?? Number.MAX_SAFE_INTEGER) - (b[`${field}_info`].order ?? Number.MAX_SAFE_INTEGER);
        if (order) return order;
        const titleOrder = a[`${field}_info`].title.localeCompare(b[`${field}_info`].title, "es");
        if (titleOrder) return titleOrder;
      }
      return 0;
    });
    for (const [collection, title] of Object.entries(data.collections)) {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.collection = collection;
      button.textContent = title;
      button.addEventListener("click", () => {
        if (selection.collection === collection) return;
        selection.collection = collection;
        selection.date = videos.find(entry => entry.collection === collection)?.date || "";
        selection.cycle = selection.scene = selection.software = selection.animation = selection.source = selection.video = "";
        updateLibrary();
      });
      collectionNav.append(button);
    }
    selection.collection = videos[0]?.collection || Object.keys(data.collections)[0];
    selection.date = videos.find(entry => entry.collection === selection.collection)?.date || "";
    const requestedVideo = new URL(window.location.href).searchParams.get("video");
    if (requestedVideo) {
      const entry = videos.find(entry => entry.id === requestedVideo);
      if (!entry) throw new Error("El video solicitado en el enlace ya no está disponible. Abre una alternativa desde Revisión de diseño para consultar el catálogo.");
      for (const field of ["collection", "date", "cycle", "scene", "software", "animation", "source"]) selection[field] = entry[field];
      selection.video = entry.id;
    }
    document.querySelector("#filters-panel").hidden = false;
    updateLibrary();
  } catch (error) {
    clearVideo();
    document.querySelector("#results-description").textContent = "No se pudo cargar la biblioteca";
    document.querySelector("#viewer-workspace").hidden = true;
    document.querySelector("#video-information").hidden = true;
    document.querySelector("#filters-panel").hidden = true;
    if (isEditorial) document.querySelector("#video-previews-section").hidden = true;
    collectionNav.replaceChildren();
    const message = document.querySelector("#catalog-error");
    message.textContent = `${error.message} Corrige el problema y vuelve a cargar la página.`;
    message.hidden = false;
  } finally {
    document.querySelector("#results-section").setAttribute("aria-busy", "false");
  }
}
loadLibrary();
