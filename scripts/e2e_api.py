"""
Start the API for end-to-end tests on a fresh, throwaway app database.

The database and audit directory under E2E_DIR (default runs/e2e) are
recreated on every start, migrated, and seeded with the demo users from the
DEMO_* environment variables (fixtures set by webapp/playwright.config.ts).

    python scripts/e2e_api.py --port 8100
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8100)
    args = parser.parse_args()

    root = Path(os.environ.get("E2E_DIR", "runs/e2e"))
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    os.environ["DATABASE_URL"] = f"sqlite:///{(root / 'app.db').as_posix()}"
    os.environ["APP_AUDIT_DIR"] = str(root / "app_audit")

    from fraudsim import appdb
    from fraudsim.api.v1.auth.users import seed_demo_users

    appdb.upgrade()
    db = appdb.open_session()
    try:
        print("seeded:", seed_demo_users(db), flush=True)
    finally:
        db.close()

    import uvicorn

    uvicorn.run("fraudsim.api.main:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
