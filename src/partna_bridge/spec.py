"""Сборка публичного контракта фактов из приложения.

Схема собирается из обработчиков, поэтому не может разойтись с ними:
в контракт попадают только пять операций и их модели.
"""

from __future__ import annotations

import json
from pathlib import Path

from partna_bridge.app import create_app
from partna_bridge.config import Settings
from partna_bridge.contract import FACTS_OPERATIONS

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "spec" / "partna-facts.v1.json"

DESCRIPTION = (
    "Факты партнёрской программы: привязка клиента к коду партнёра, участник, "
    "заказ, возврат и ссылка партнёра. Ключ тенанта передаётся на сервере, "
    "в браузер не попадает."
)


def build_spec() -> dict:
    app = create_app(
        Settings(engine_url="https://engine.example", outbox_mode="inline")
    )
    full = app.openapi()
    schemas = full.get("components", {}).get("schemas", {})

    paths: dict = {}
    used: set[str] = set()
    for method, path in FACTS_OPERATIONS:
        operation = full["paths"][path][method]
        paths.setdefault(path, {})[method] = operation
        for ref in _refs(operation):
            used.add(ref)

    pending = list(used)
    while pending:
        name = pending.pop()
        for ref in _refs(schemas.get(name, {})):
            if ref not in used:
                used.add(ref)
                pending.append(ref)

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Partna facts",
            "version": "1.0.0",
            "description": DESCRIPTION,
        },
        "paths": paths,
        "components": {"schemas": {name: schemas[name] for name in sorted(used)}},
    }


def _refs(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "$ref" and isinstance(item, str):
                found.add(item.rsplit("/", 1)[-1])
            else:
                found |= _refs(item)
    elif isinstance(value, list):
        for item in value:
            found |= _refs(item)
    return found


def render() -> str:
    return json.dumps(build_spec(), ensure_ascii=False, indent=2) + "\n"
