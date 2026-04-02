import json
from pathlib import Path

import yaml


def read_json(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def write_json(path: str, data, indent: int = 2):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def read_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def read_text(path: str) -> str:
    with open(path) as f:
        return f.read()


def write_text(path: str, content: str):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
