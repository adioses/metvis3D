"""Lee los parámetros YAML de los productos meteorológicos."""

from pathlib import Path
import yaml


def load_yaml_configuration(configuration_file: Path, description: str) -> dict:
    """Lee una configuración YAML y detiene el flujo si no es un mapa."""

    if not configuration_file.exists():
        raise RuntimeError(f"No existe la configuración {description}: {configuration_file}")

    with configuration_file.open(encoding="utf-8") as source:
        configuration = yaml.safe_load(source)

    if not isinstance(configuration, dict):
        raise RuntimeError(f"La configuración {description} debe contener claves YAML: {configuration_file}")
    return configuration


def require_value(configuration: dict, path: tuple[str, ...], description: str) -> object:
    """Obtiene un valor obligatorio e informa su ruta científica si falta."""

    current: object = configuration
    for key in path:
        if not isinstance(current, dict) or key not in current:
            joined_path = ".".join(path)
            raise RuntimeError(f"Falta '{joined_path}' en la configuración {description}.")
        current = current[key]
    return current


