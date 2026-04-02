import json
from pathlib import Path

import yaml


def load_spec(path: str) -> dict:
    """Load an OpenAPI spec from a YAML or JSON file."""
    with open(path) as f:
        content = f.read()
    suffix = Path(path).suffix.lower()
    if suffix in (".yaml", ".yml"):
        return yaml.safe_load(content)
    elif suffix == ".json":
        return json.loads(content)
    # Unknown extension: try YAML, fall back to JSON
    try:
        return yaml.safe_load(content)
    except Exception:
        return json.loads(content)


def detect_format(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in (".yaml", ".yml"):
        return "yaml"
    elif suffix == ".json":
        return "json"
    return "yaml"


def extract_openapi_version(spec: dict) -> str:
    if "openapi" in spec:
        return str(spec["openapi"])
    if "swagger" in spec:
        return str(spec["swagger"])
    return "unknown"


def extract_info(spec: dict) -> dict:
    info = spec.get("info", {}) or {}
    return {
        "title": info.get("title", "") or "",
        "version": info.get("version", "") or "",
        "description": info.get("description", "") or "",
    }
