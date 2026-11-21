// La preferencia se aplica antes de dibujar la página para evitar destellos.
const savedTheme = localStorage.getItem("metvis3d-theme");
document.documentElement.dataset.theme = savedTheme === "light" ? "light" : "dark";
