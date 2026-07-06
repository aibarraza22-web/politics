"""Repo paths and API-key loading.

All code locates the repo root from this file's position, so scripts, tests,
and Quarto chunks (which execute with cwd inside paper/) resolve the same
paths. API keys come from .env at the repo root (see .env.example).
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
FINAL_DIR = DATA_DIR / "final"
PAPER_DIR = REPO_ROOT / "paper"
FIGURES_DIR = PAPER_DIR / "figures"
DUCKDB_PATH = DATA_DIR / "c2c.duckdb"

load_dotenv(REPO_ROOT / ".env")


class MissingApiKeyError(RuntimeError):
    pass


def api_key(name: str) -> str:
    """Fetch a required API key from the environment / .env.

    Usage: api_key("EIA_API_KEY"), api_key("NREL_API_KEY").
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingApiKeyError(
            f"{name} is not set. Copy .env.example to .env at the repo root "
            f"and fill in {name} (both keys are free — see .env.example for "
            "signup URLs)."
        )
    return value
