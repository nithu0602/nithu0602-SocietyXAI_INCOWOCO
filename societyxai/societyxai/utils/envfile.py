from __future__ import annotations

from pathlib import Path


def load_env_file(*candidates: str | Path) -> None:
    """Load KEY=VALUE pairs into os.environ without overwriting existing values."""
    import os

    for candidate in candidates:
        path = Path(candidate)
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
