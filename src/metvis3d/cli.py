"""Punto de entrada de la línea de comandos.

Los subcomandos de inventario, estandarización y render se implementarán de
forma incremental. Por ahora se conserva un punto de entrada estable.
"""

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="metvis")
    parser.add_argument("--version", action="version", version="metvis3d 0.1.0")
    parser.parse_args()
    parser.print_help()
