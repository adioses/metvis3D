"""Lanzar la preparación manual de videos desde su configuración YAML."""

import argparse

from publication import run_publication

parser = argparse.ArgumentParser(description="Preparar copias verificadas y miniaturas locales.")
parser.add_argument("--config", default="config/publication.yaml", help="Configuración relativa a website/ o absoluta.")
if __name__ == "__main__":
    run_publication(parser.parse_args().config)
