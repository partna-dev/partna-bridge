"""Выгрузка контракта: uv run python scripts/export_spec.py [--check]."""

from __future__ import annotations

import sys
from pathlib import Path

from partna_bridge.spec import TARGET, render

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> int:
    body = render()
    if "--check" in argv:
        if not TARGET.is_file() or TARGET.read_text(encoding="utf-8") != body:
            print(f"contract is out of date: run {sys.argv[0]}", file=sys.stderr)
            return 1
        print("contract is up to date")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(body, encoding="utf-8")
    print(f"written {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
