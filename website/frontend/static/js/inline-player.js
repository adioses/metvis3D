const video = document.querySelector("#main-video");
const playbackError = document.querySelector("#playback-error");
const download = document.querySelector("#download-video");
const details = document.querySelector("#video-details");
const extra = document.querySelector("#extra-metadata");
const loop = document.querySelector("#loop-control");
const speed = document.querySelector("#speed-control");
const settings = JSON.parse(document.querySelector("#website-settings").textContent).playback;
let currentVideoId = "";

export function formatDate(date) {
  return new Intl.DateTimeFormat("es-PE", {day: "2-digit", month: "short", year: "numeric", timeZone: "UTC"}).format(new Date(`${date}T00:00:00Z`));
}

function addDetail(label, value) {
  const term = document.createElement("dt");
  const description = document.createElement("dd");
  term.textContent = label;
  description.textContent = value;
  details.append(term, description);
}

function addExtra(label, value) {
  const title = document.createElement("h3");
  const paragraph = document.createElement("p");
  title.textContent = label;
  paragraph.textContent = value;
  extra.append(title, paragraph);
}

function showPlaybackError(message) {
  playbackError.textContent = message;
  playbackError.hidden = false;
}

export function clearVideo() {
  currentVideoId = "";
  video.pause();
  video.removeAttribute("src");
  video.removeAttribute("poster");
  video.load();
  playbackError.hidden = true;
  download.removeAttribute("href");
}

export function showVideo(entry) {
  if (entry.id === currentVideoId) return;
  clearVideo();
  currentVideoId = entry.id;

  document.querySelector("#video-title").textContent = entry.animation_info.title;
  if (!document.body.classList.contains("design-editorial")) {
    document.querySelector("#video-context").textContent = `${entry.source_info.title} · ${entry.scene_info.title} · ${entry.software_info.title}`;
    document.querySelector("#video-reference").textContent = `${entry.reference_label}: ${formatDate(entry.date)} · ${entry.cycle}:00 UTC`;
  }
  const description = document.querySelector("#animation-description");
  description.textContent = entry.animation_info.description || "";
  description.hidden = !description.textContent;
  details.replaceChildren();
  addDetail(entry.reference_label, `${formatDate(entry.date)} · ${entry.cycle}:00 UTC`);
  addDetail("Escena", entry.scene_info.title);
  addDetail("Modelo / fuente", entry.source_info.description || entry.source_info.title);
  addDetail("Herramienta", entry.software_info.title);
  const metadata = entry.metadata;
  if (metadata.playback?.duration_seconds) addDetail("Duración", `${metadata.playback.duration_seconds.toLocaleString("es-PE", {maximumFractionDigits: 2})} s`);
  if (metadata.playback?.width && metadata.playback?.height) addDetail("Resolución", `${metadata.playback.width} × ${metadata.playback.height}`);
  extra.replaceChildren();
  if (metadata.variables?.length) addExtra("Variables", metadata.variables.map(item => `${item.title || item.name}${item.units ? ` (${item.units})` : ""}`).join(" · "));
  if (metadata.period) addExtra("Periodo representado", `${metadata.period.start} — ${metadata.period.end}`);
  if (metadata.notes) addExtra("Notas", metadata.notes);

  download.href = entry.download_url;
  download.download = entry.filename;
  document.querySelector("#poster-note").hidden = Boolean(entry.thumbnail_url);
  if (entry.thumbnail_url) video.poster = entry.thumbnail_url;
  // Sólo se carga el video elegido; la reproducción comienza con el control del usuario.
  video.src = entry.video_url;
  video.loop = loop.checked;
  video.defaultPlaybackRate = Number(speed.value);
  video.playbackRate = Number(speed.value);
}

settings.speeds.forEach(value => speed.add(new Option(`${value}×`, value)));
speed.value = String(settings.initial_speed);
loop.checked = settings.loop;
loop.addEventListener("change", () => { video.loop = loop.checked; });
speed.addEventListener("change", () => {
  video.defaultPlaybackRate = Number(speed.value);
  video.playbackRate = Number(speed.value);
});
video.addEventListener("play", () => { document.querySelector("#poster-note").hidden = true; });
video.addEventListener("error", () => {
  if (currentVideoId) showPlaybackError("No se pudo reproducir el video seleccionado. El archivo puede haber sido retirado o su formato no ser compatible con este navegador. Actualiza el catálogo.");
});

document.querySelector("#fullscreen-control").addEventListener("click", async () => {
  if (!video.requestFullscreen) {
    showPlaybackError("Este navegador no ofrece pantalla completa desde este control.");
    return;
  }
  try { await video.requestFullscreen(); }
  catch (error) { showPlaybackError(`No se pudo abrir la pantalla completa: ${error.message}`); }
});

download.addEventListener("click", async event => {
  event.preventDefault();
  // La fecha o el modelo pueden cambiar mientras se comprueba el archivo elegido.
  const videoId = currentVideoId;
  const videoUrl = download.href;
  const filename = download.download;
  try {
    const response = await fetch(videoUrl, {method: "HEAD"});
    if (!response.ok) throw new Error(response.status === 404 ? "El archivo ya no está disponible. Actualiza el catálogo." : `La descarga devolvió HTTP ${response.status}.`);
    const link = document.createElement("a");
    link.href = videoUrl;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
  } catch (error) {
    const message = `No se pudo descargar ${filename}: ${error.message}`;
    if (videoId === currentVideoId) showPlaybackError(message);
    else window.alert(message);
  }
});

// Al salir de una alternativa se detiene su video, incluso si el navegador conserva la página.
window.addEventListener("pagehide", () => video.pause());
