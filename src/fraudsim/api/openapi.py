"""The API's OpenAPI document, serialised deterministically for the committed contract."""

from __future__ import annotations

import json
from typing import Any


def openapi_dict() -> dict[str, Any]:
    from fraudsim.api.main import app

    app.openapi_schema = None  # rebuild from the current routes
    return app.openapi()


def openapi_json() -> str:
    return json.dumps(openapi_dict(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
