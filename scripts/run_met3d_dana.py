"""Prepara, abre o renderiza la DANA con Met.3D."""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from visualize.met3D.cli import run_animation


if __name__ == "__main__":
    run_animation(PROJECT_ROOT, "south_america_dana.yaml", "Explora o renderiza la DANA con Met.3D.")
