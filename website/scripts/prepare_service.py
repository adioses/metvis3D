"""Preparar la unidad systemd sin instalarla ni solicitar contraseñas."""

import argparse

from operation import run_service_preparation

parser = argparse.ArgumentParser(description="Preparar el servicio local de Visualizaciones 3D.")
parser.add_argument("--config", default="config/website.yaml", help="Configuración relativa a website/ o absoluta.")
if __name__ == "__main__":
    run_service_preparation(parser.parse_args().config)
