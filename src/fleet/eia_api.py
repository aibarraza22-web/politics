"""Minimal EIA v2 API client (real mode).

STATUS: written against the documented API shape (api.eia.gov/v2, JSON,
`response.data` rows, 5000-row pages) but NOT yet verified against a live
response — this build environment has no route to api.eia.gov. Per CLAUDE.md
("inspect real API responses before writing parsers"), the first run on a
networked machine must eyeball a raw response and update SOURCES.md before
results are trusted. See SOURCES.md `eia930`/`eia923`.
"""

from __future__ import annotations

from typing import Any

import requests

from src.config import api_key

BASE = "https://api.eia.gov/v2"
PAGE = 5000


def get_paged(route: str, params: dict[str, Any]) -> list[dict]:
    """GET all pages of an EIA v2 data route; returns response.data rows."""
    rows: list[dict] = []
    offset = 0
    while True:
        q = {
            "api_key": api_key("EIA_API_KEY"),
            "offset": offset,
            "length": PAGE,
            **params,
        }
        resp = requests.get(f"{BASE}/{route}/data/", params=q, timeout=120)
        resp.raise_for_status()
        payload = resp.json()["response"]
        batch = payload["data"]
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < PAGE or offset >= int(payload.get("total", 0)):
            return rows
