"""Preparación del servicio Linux con las rutas del ambiente web instalado."""

import grp
import json
import os
import pwd
import sys
from datetime import datetime
from pathlib import Path
from string import Template
from zoneinfo import ZoneInfo

from catalog import CatalogError, WEBSITE_ROOT, read_website_config, website_path


def run_service_preparation(config_path="config/website.yaml"):
    """Leer la configuración y escribir una unidad systemd lista para instalar."""
    # El servicio trabaja con la cuenta propietaria del proyecto y su ambiente Conda.
    config_path = website_path(config_path)
    settings = read_website_config(config_path)
    python_executable = Path(sys.executable).absolute()
    if os.getuid() == 0:
        raise CatalogError("Prepara el servicio como el usuario del proyecto, sin ejecutar Python con sudo.")
    account = pwd.getpwuid(os.getuid())
    template_path = WEBSITE_ROOT / "deploy/metvis3d-web.service.in"
    unit_path = WEBSITE_ROOT / ".local/metvis3d-web.service"
    paths = {
        "website_root": WEBSITE_ROOT,
        "python_executable": python_executable,
        "website_script": WEBSITE_ROOT / "scripts/run_website.py",
        "website_config": config_path,
    }

    # Las rutas concretas pertenecen al archivo generado, no a la plantilla versionada.
    substitutions = {key: str(path).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%")
                     for key, path in paths.items()}
    substitutions["website_root"] = str(WEBSITE_ROOT).replace("%", "%%")
    for key in ("python_executable", "website_script", "website_config"):
        substitutions[key] = substitutions[key].replace("$", "$$")
    substitutions.update(service_user=account.pw_name, service_group=grp.getgrgid(account.pw_gid).gr_name)
    unit = Template(template_path.read_text(encoding="utf-8")).substitute(substitutions)
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(unit, encoding="utf-8")

    # El registro distingue preparar una unidad de instalarla y comprobar el arranque.
    report = {"date_lima": datetime.now(ZoneInfo("America/Lima")).isoformat(),
              "status": "prepared", "unit": str(unit_path), "config": str(config_path),
              "python": str(python_executable), "user": account.pw_name,
              "host": settings["server"]["host"], "port": settings["server"]["port"],
              "installed": False, "reboot_verified": False}
    report_path = WEBSITE_ROOT / "validation/service-preparation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Unidad preparada: {unit_path}")
    print(f"Usuario: {account.pw_name}; Python: {python_executable}")
    print("La unidad todavía debe instalarse y comprobarse mediante systemd.")
    return unit_path
