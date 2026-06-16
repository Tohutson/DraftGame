"""
Offline-first wrapper for future nflreadpy/nflverse imports.

Gameplay should use cached JSON/parquet files built by scripts, not live calls.
Install nflreadpy and expand this module when replacing the sample career data
with full nflverse-derived summaries.
"""


def nflreadpy_available() -> bool:
    try:
        import nflreadpy  # noqa: F401
    except ImportError:
        return False
    return True


def load_career_summaries(*_args, **_kwargs):
    if not nflreadpy_available():
        raise RuntimeError(
            "nflreadpy is not installed. Install it only when rebuilding cached NFL career data."
        )
    raise NotImplementedError("nflverse career summary import is a future data-pipeline step.")

