"""The .env loader that keeps local credentials out of code."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fraudsim.envfile import load_dotenv

ENV_FILE = """# comment
FS_A=one
export FS_B='two words'
FS_C="three"
FS_EMPTY=
not a pair
FS_SET=file
"""


def test_loads_unset_keys_and_never_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(os, "environ", {"FS_SET": "shell"})  # isolated copy, restored after
    env = tmp_path / ".env"
    env.write_text(ENV_FILE, encoding="utf-8")
    assert sorted(load_dotenv(env)) == ["FS_A", "FS_B", "FS_C"]
    assert os.environ == {"FS_SET": "shell", "FS_A": "one", "FS_B": "two words", "FS_C": "three"}


def test_missing_file_is_fine(tmp_path: Path) -> None:
    assert load_dotenv(tmp_path / "absent.env") == []


def test_neo4j_client_has_no_default_password(monkeypatch: pytest.MonkeyPatch) -> None:
    from fraudsim.graph.neo4j_client import Neo4jClient

    monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
    with pytest.raises(ValueError, match="NEO4J_PASSWORD"):
        Neo4jClient()
