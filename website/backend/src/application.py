"""Aplicación local de consulta, reproducción y descarga de videos publicados."""

from pathlib import Path

from flask import Blueprint, Flask, abort, jsonify, render_template, request, send_file, url_for
from werkzeug.exceptions import HTTPException

from catalog import (CatalogError, WEBSITE_ROOT, parse_video_name, published_file,
                     read_catalog, read_website_config)


def create_app(config_path=None):
    """Configurar las rutas de interfaz, catálogo y entrega de archivos locales."""
    settings = read_website_config(config_path)
    prefix = settings["url_prefix"]
    app = Flask(__name__, template_folder=str(WEBSITE_ROOT / "frontend/templates"),
                static_folder=str(WEBSITE_ROOT / "frontend/static"), static_url_path=f"{prefix}/static")
    app.config["WEBSITE_SETTINGS"] = settings
    routes = Blueprint("website", __name__, url_prefix=prefix)

    @routes.get("/")
    def index():
        return render_template("index.html", settings=settings)

    @routes.get("/api/videos")
    def videos():
        try:
            entries = read_catalog(settings)
        except CatalogError as error:
            app.logger.error("No se pudo reconstruir el catálogo: %s", error)
            # Los registros conservan el contexto local; la respuesta no expone rutas absolutas.
            message = str(error).replace(str(settings["video_root"]), "[publicación]").replace(str(WEBSITE_ROOT), "[website]")
            return jsonify(error=f"Catálogo detenido: {message}"), 422
        for entry in entries:
            arguments = {"collection": entry["collection"], "filename": entry["filename"]}
            entry["video_url"] = url_for("website.media", **arguments)
            entry["download_url"] = url_for("website.download", **arguments)
            entry["thumbnail_url"] = url_for("website.media", collection=entry["collection"],
                                             filename=Path(entry["filename"]).stem + ".jpg") if entry.pop("has_thumbnail") else None
        return jsonify(videos=entries, collections=settings["collections"], demonstration=settings["demonstration"])

    def media_path(collection, filename, suffixes):
        if Path(filename).suffix not in suffixes:
            abort(404, description="Formato de archivo no disponible.")
        try:
            parse_video_name(filename if filename.endswith(".mp4") else Path(filename).stem + ".mp4")
            path = published_file(settings["video_root"], collection, filename)
        except CatalogError:
            abort(404, description="Archivo o colección no disponible.")
        if not path.is_file():
            abort(404, description="El archivo ya no está disponible. Actualiza el catálogo.")
        return path

    @routes.get("/media/<collection>/<filename>")
    def media(collection, filename):
        path = media_path(collection, filename, {".mp4", ".jpg"})
        return send_file(path, mimetype="video/mp4" if path.suffix == ".mp4" else "image/jpeg",
                         conditional=True, max_age=0)

    @routes.get("/download/<collection>/<filename>")
    def download(collection, filename):
        path = media_path(collection, filename, {".mp4"})
        return send_file(path, mimetype="video/mp4", as_attachment=True, download_name=filename,
                         conditional=True, max_age=0)

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.description), error.code

    @app.errorhandler(500)
    def general_error(error):
        # Flask registra la excepción original completa antes de entregar este mensaje.
        return jsonify(error="Ocurrió un error general. Revisa el registro del servicio para consultar el detalle original."), 500

    @app.after_request
    def response_headers(response):
        # Una recarga refleja el disco; los fragmentos de video mantienen su entrega condicional.
        response.headers["Cache-Control"] = "no-store" if "/api/" in request.path else "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    app.register_blueprint(routes)
    return app
