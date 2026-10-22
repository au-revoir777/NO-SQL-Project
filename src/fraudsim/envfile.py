"""
Minimal .env loader: KEY=VALUE lines, `#` comments, optional quotes.

Variables already set in the environment win, so CI and shell exports override
the file. Used by the CLI and seed.py so local credentials (NEO4J_PASSWORD,
JWT_SECRET, ...) live only in the git-ignored .env, never in code.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> list[str]:
    """Set unset variables from `path`; return the names that were set."""
    p = Path(path)
    if not p.is_file():
        return []
    loaded = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
