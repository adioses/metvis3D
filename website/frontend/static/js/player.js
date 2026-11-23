const dialog = document.querySelector("#player-dialog");
const video = document.querySelector("#main-video");
const playbackError = document.querySelector("#playback-error");
const download = document.querySelector("#download-video");
const details = document.querySelector("#video-details");
const extra = document.querySelector("#extra-metadata");
const loop = document.querySelector("#loop-control");
const speed = document.querySelector("#speed-control");
const settings = JSON.parse(document.querySelector("#website-settings").textContent).playback;

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
  const title = document.createElement("h4");
  const paragraph = document.createElement("p");
  title.textContent = label;
  paragraph.textContent = value;
  extra.append(title, paragraph);
}

function showPlaybackError(message) {
  playbackError.textContent = message;
  playbackError.hidden = false;
}

export function openPlayer(entry) {
  video.pause();
  video.removeAttribute("src");
  video.load();
  playbackError.hidden = true;
  document.querySelector("#player-title").textContent = entry.animation_info.title;
  document.querySelector("#player-eyebrow").textContent = `${entry.source_info.title} · ${entry.scene_info.title} · ${entry.software_info.title}`;
  const description = document.querySelector("#animation-description");
  description.textContent = entry.animation_info.description || "";
  description.hidden = !description.textContent;
  details.replaceChildren();
  addDetail(entry.reference_label, `${formatDate(entry.date)} · ${entry.cycle}:00 UTC`);
  addDetail("Escena", entry.scene_info.title);
  addDetail("Fuente", entry.source_info.description || entry.source_info.title);
  addDetail("Herramienta", entry.software_info.title);
  const metadata = entry.metadata;
  if (metadata.playback?.duration_seconds) addDetail("Duración del video", `${metadata.playback.duration_seconds.toLocaleString("es-PE", {maximumFractionDigits: 2})} s`);
  if (metadata.playback?.width && metadata.playback?.height) addDetail("Resolución", `${metadata.playback.width} × ${metadata.playback.height}`);
  extra.replaceChildren();
  if (metadata.variables?.length) addExtra("Variables", metadata.variables.map(item => `${item.title || item.name}${item.units ? ` (${item.units})` : ""}`).join(" · "));
  if (metadata.period) addExtra("Periodo representado", `${metadata.period.start} — ${metadata.period.end}`);
  if (metadata.notes) addExtra("Notas", metadata.notes);
  download.href = entry.download_url;
  download.download = entry.filename;
  video.poster = entry.thumbnail_url || "";
  loop.checked = settings.loop;
  video.loop = settings.loop;
  speed.value = String(settings.initial_speed);
  video.playbackRate = settings.initial_speed;
  video.src = entry.video_url;
  dialog.showModal();
  // La apertura es una acción explícita del usuario; nunca se reproducen tarjetas.
  video.play().catch(error => {
    if (dialog.open && video.getAttribute("src") === entry.video_url) {
      showPlaybackError(`No se pudo iniciar el video: ${error.message}. Actualiza el catálogo si el archivo fue retirado.`);
    }
  });
}

settings.speeds.forEach(value => speed.add(new Option(`${value}×`, value)));
loop.addEventListener("change", () => { video.loop = loop.checked; });
speed.addEventListener("change", () => { video.playbackRate = Number(speed.value); });
video.addEventListener("error", () => showPlaybackError("No se pudo reproducir el video. El archivo puede haber sido retirado o su formato no ser compatible con este navegador. Actualiza el catálogo."));
document.querySelector("#close-player").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
dialog.addEventListener("close", () => {
  video.pause();
  video.removeAttribute("src");
  video.removeAttribute("poster");
  video.load();
  playbackError.hidden = true;
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
  // Comprobar disponibilidad antes de iniciar la descarga, sin leer el MP4 completo.
  event.preventDefault();
  try {
    const response = await fetch(download.href, {method: "HEAD"});
    if (!response.ok) throw new Error(response.status === 404 ? "El archivo ya no está disponible. Actualiza el catálogo." : `La descarga devolvió HTTP ${response.status}.`);
    const link = document.createElement("a");
    link.href = download.href;
    link.download = download.download;
    document.body.append(link);
    link.click();
    link.remove();
  } catch (error) { showPlaybackError(error.message); }
});
