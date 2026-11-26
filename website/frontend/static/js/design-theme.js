// Las propuestas parten del tema claro y respetan una preferencia ya elegida.
const savedDesignTheme = localStorage.getItem("metvis3d-theme");
document.documentElement.dataset.theme = savedDesignTheme === "dark" ? "dark" : "light";
const designThemeButton = document.querySelector("#theme-toggle");
function updateDesignThemeLabel() {
  const label = document.documentElement.dataset.theme === "dark" ? "Tema claro" : "Tema oscuro";
  document.querySelector("#theme-label").textContent = label;
  designThemeButton.setAttribute("aria-label", `Cambiar a ${label.toLowerCase()}`);
}
updateDesignThemeLabel();
designThemeButton.addEventListener("click", () => {
  document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem("metvis3d-theme", document.documentElement.dataset.theme);
  updateDesignThemeLabel();
});
