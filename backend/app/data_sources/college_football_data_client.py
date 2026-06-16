"""
Offline-first CollegeFootballData client placeholder.

The MVP runs without an API key from bundled cached data. Use this module from
build_draft_dataset.py when adding a full CollegeFootballData import.
"""

import os


def get_api_key() -> str | None:
    return os.getenv("COLLEGE_FOOTBALL_DATA_API_KEY")


def client_available() -> bool:
    return bool(get_api_key())


def load_college_stats(*_args, **_kwargs):
    if not client_available():
        raise RuntimeError("COLLEGE_FOOTBALL_DATA_API_KEY is not set.")
    raise NotImplementedError("CollegeFootballData import is a future data-pipeline step.")

