"""
Freeze the evidence the paper rests on: hash every result file and model,
check that the committed LaTeX tables regenerate byte-identically from the
CSVs, and write it all to one JSON file.

    python scripts/baseline_snapshot.py --out docs/audit/m0_baseline.json
    python scripts/baseline_snapshot.py --check docs/audit/m0_baseline.json

`--check` compares the current tree with a saved snapshot and exits non-zero
if any result, model or generated table changed, so later milestones can prove
that existing evidence was not altered (new files are reported, not failed).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ["results", "models", "docs/paper/tables"]


def sha256(path: Path) -> str:
    # Line endings normalised so a Windows checkout and CI hash the same.
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rows(path: Path) -> int | None:
    if path.suffix != ".csv":
        return None
    with path.open(encoding="utf-8", newline="") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def files() -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for top in EVIDENCE:
        for p in sorted((ROOT / top).rglob("*")):
            if p.is_file():
                out[p.relative_to(ROOT).as_posix()] = {"sha256": sha256(p), "rows": rows(p)}
    return out


def tables_reproducible() -> dict[str, bool]:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [sys.executable, "-m", "fraudsim.experiments.latex_export",
             "--results-dir", "results", "--output-dir", tmp],
            check=True, capture_output=True, cwd=ROOT,
        )  # fmt: skip
        return {
            p.name: (ROOT / "docs/paper/tables" / p.name).is_file()
            and sha256(p) == sha256(ROOT / "docs/paper/tables" / p.name)
            for p in sorted(Path(tmp).iterdir())
        }


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=ROOT).stdout.strip()


def snapshot() -> dict[str, object]:
    return {
        "git_commit": git("rev-parse", "HEAD"),
        "git_dirty_paths": [line[3:] for line in git("status", "--porcelain").splitlines()],
        "python": sys.version.split()[0],
        "files": files(),
        "tables_regenerate_identically": tables_reproducible(),
    }


def check(saved_path: Path) -> int:
    saved = json.loads(saved_path.read_text(encoding="utf-8"))
    now = snapshot()
    old_files, new_files = saved["files"], now["files"]
    assert isinstance(old_files, dict) and isinstance(new_files, dict)
    changed = [k for k in old_files if k in new_files and old_files[k] != new_files[k]]
    missing = [k for k in old_files if k not in new_files]
    added = [k for k in new_files if k not in old_files]
    tables = now["tables_regenerate_identically"]
    assert isinstance(tables, dict)
    stale = [k for k, ok in tables.items() if not ok]
    for label, items in (("changed", changed), ("missing", missing), ("stale table", stale)):
        for k in items:
            print(f"{label}: {k}")
    for k in added:
        print(f"new (ok): {k}")
    print(f"{len(old_files)} files in snapshot; {len(changed)} changed, {len(missing)} missing, "
          f"{len(added)} new; {len(stale)} stale tables")  # fmt: skip
    return 1 if changed or missing or stale else 0


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--out", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    if args.check:
        sys.exit(check(args.check))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(snapshot(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
