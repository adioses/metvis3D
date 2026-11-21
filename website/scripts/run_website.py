"""Iniciar Gunicorn con las rutas del ambiente Conda independiente."""

import argparse
import os
import sys
from pathlib import Path

from catalog import read_website_config, website_path


def run_website(config_path):
    """Leer la configuración y ejecutar el servidor local sin depurador."""
    settings = read_website_config(config_path)
    server = settings["server"]
    config_path = website_path(config_path)
    os.environ["METVIS3D_WEBSITE_CONFIG"] = str(config_path)
    executable = Path(sys.executable).parent / "gunicorn"
    print(f"Visualizaciones 3D: http://{server['host']}:{server['port']}{settings['url_prefix']}/", flush=True)
    os.execv(str(executable), [str(executable), "--bind", f"{server['host']}:{server['port']}",
                              "--workers", str(server["workers"]), "--threads", str(server["threads"]),
                              "--timeout", str(server["timeout"]), "--access-logfile", "-", "--error-logfile", "-",
                              "--no-control-socket", "--forwarded-allow-ips", "", "--forwarder-headers", "",
                              "application:create_app()"])


parser = argparse.ArgumentParser(description="Servir Visualizaciones 3D mediante Gunicorn.")
parser.add_argument("--config", default="config/website.yaml", help="Configuración relativa a website/ o absoluta.")
if __name__ == "__main__":
    run_website(parser.parse_args().config)
