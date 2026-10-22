"""
Run provenance for experiments (M0 audit, R3).

Every experiment run appends one entry to <out_dir>/manifest.json under
"grids", including runs that fail:

    with recorded(out_dir, "e4_scale", {"sizes": [...], "seeds": [...]}):
        ... write rows to out_dir/results.csv ...

The entry holds the caller's details plus: status ("complete" or "failed"),
error type and message, UTC start/end times, wall time, rows appended to
results.csv during the run, git commit and whether the tree had uncommitted
changes, Python and key library versions, and the CPU count. Existing result
directories are never rewritten: entries are only appended.
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import time
import traceback
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
LIBRARIES = ("numpy", "pandas", "scipy", "scikit-learn", "networkx", "neo4j", "redis")


def _git(*args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], capture_output=True, text=True, cwd=REPO_ROOT, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def code_version() -> dict[str, Any]:
    """Git commit and dirty flag (None when not run from a git checkout)."""
    status = _git("status", "--porcelain", "--untracked-files=no")
    return {
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if status is None else bool(status),
    }


def environment() -> dict[str, Any]:
    versions = {}
    for lib in LIBRARIES:
        try:
            versions[lib] = metadata.version(lib)
        except metadata.PackageNotFoundError:
            versions[lib] = None
    return {
        "python": platform.python_version(),
        "platform": platform.platform(terse=True),
        "cpu_count": os.cpu_count(),
        "libraries": versions,
    }


def repo_relative(path: Path | str) -> str:
    """Path relative to the repository when inside it (manifests stay portable)."""
    p = Path(path).resolve()
    try:
        return p.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return p.as_posix()


def _csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return max(sum(1 for _ in f) - 1, 0)


def append_entry(out_dir: Path, entry: dict[str, Any]) -> None:
    path = Path(out_dir) / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"grids": []}
    manifest.setdefault("grids", []).append(entry)
    path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")


@contextmanager
def recorded(out_dir: Path, experiment: str, details: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """
    Record one run in out_dir/manifest.json, whether it completes or raises.
    The yielded dict is the entry: callers may add fields (e.g. "model") to it.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = out_dir / "results.csv"
    rows_before = _csv_rows(results)
    entry: dict[str, Any] = {"experiment": experiment, **details}
    started = datetime.now(UTC)
    t0 = time.perf_counter()
    status, error = "complete", None
    try:
        yield entry
    except BaseException as exc:
        status = "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
        error = {
            "type": type(exc).__name__,
            "message": str(exc)[:2000],
            "traceback_tail": traceback.format_exc().splitlines()[-6:],
        }
        raise
    finally:
        entry.update(
            {
                "status": status,
                "error": error,
                "started_at": started.isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "wall_s": round(time.perf_counter() - t0, 3),
                "rows": _csv_rows(results) - rows_before,
                **code_version(),
                **environment(),
            }
        )
        append_entry(out_dir, entry)
