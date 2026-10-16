#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from credit.api import app  # noqa: E402


def downgrade(node: Any) -> Any:
    if isinstance(node, list):
        return [downgrade(item) for item in node]
    if not isinstance(node, dict):
        return node

    node = {key: downgrade(value) for key, value in node.items()}

    variants = node.get("anyOf")
    if isinstance(variants, list) and {"type": "null"} in variants:
        rest = [v for v in variants if v != {"type": "null"}]
        del node["anyOf"]
        if len(rest) == 1:
            node.update(rest[0])
        else:
            node["anyOf"] = rest
        node["nullable"] = True

    for key, flag in (("exclusiveMinimum", "minimum"), ("exclusiveMaximum", "maximum")):
        if isinstance(node.get(key), (int, float)) and not isinstance(node[key], bool):
            node[flag] = node.pop(key)
            node[key] = True

    if "const" in node:
        node["enum"] = [node.pop("const")]

    if isinstance(node.get("examples"), list) and "type" in node:
        examples = node.pop("examples")
        if examples:
            node["example"] = examples[0]

    if node.get("type") == "number" and "format" not in node:
        node["format"] = "double"

    return node


def rename_operations(spec: dict[str, Any]) -> None:
    names = {
        (route.path, method.lower()): route.name
        for route in app.routes
        if getattr(route, "include_in_schema", False)
        for method in getattr(route, "methods", ())
    }
    for path, ops in spec["paths"].items():
        for method, op in ops.items():
            if (path, method) in names:
                name = names[(path, method)]
                op["operationId"] = f"get_{name}" if method == "get" else name


def main() -> None:
    spec = downgrade(app.openapi())
    spec["openapi"] = "3.0.3"
    rename_operations(spec)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "openapi.json"
    out.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
