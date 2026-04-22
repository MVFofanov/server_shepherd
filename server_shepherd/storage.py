from __future__ import annotations

import json
from pathlib import Path


def read_last_jsonl(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None

    last_line = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                last_line = stripped

    if not last_line:
        return None

    return json.loads(last_line)


def append_jsonl(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":")) + "\n")
