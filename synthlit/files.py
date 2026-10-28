"""Small file helpers (UTF-8, files always closed)."""
import json


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
