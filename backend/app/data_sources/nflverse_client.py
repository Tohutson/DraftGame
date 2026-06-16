import json
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List

from app.core.config import Settings, ensure_data_dirs, get_settings


class MissingNFLReadPy(RuntimeError):
    pass


def nflreadpy_available() -> bool:
    try:
        import nflreadpy  # noqa: F401
    except ImportError:
        return False
    return True


def _records_from_frame(frame: Any) -> List[Dict[str, Any]]:
    if hasattr(frame, "to_dicts"):
        return frame.to_dicts()
    if hasattr(frame, "to_dict"):
        return frame.to_dict(orient="records")
    if isinstance(frame, list):
        return frame
    return []


class NFLVerseClient:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        ensure_data_dirs(self.settings)
        self.cache_dir = self.settings.raw_dir / "nflverse"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return nflreadpy_available()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _load_cached_or_call(
        self, key: str, loader: Callable[[], List[Dict[str, Any]]], force: bool = False
    ) -> List[Dict[str, Any]]:
        path = self._cache_path(key)
        if path.exists() and not force:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        payload = loader()
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
        return payload

    def _nflreadpy_call(self, names: Iterable[str], *args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        if not self.available:
            raise MissingNFLReadPy("nflreadpy is not installed. Install it to build real NFL data.")
        import nflreadpy

        for name in names:
            fn = getattr(nflreadpy, name, None)
            if callable(fn):
                return _records_from_frame(fn(*args, **kwargs))
        raise AttributeError(f"Installed nflreadpy does not expose any of: {', '.join(names)}")

    def available_functions(self) -> List[str]:
        if not self.available:
            return []
        import nflreadpy

        return sorted(
            name
            for name in dir(nflreadpy)
            if callable(getattr(nflreadpy, name, None))
            and any(token in name.lower() for token in ("load", "import", "read"))
        )

    def draft_picks(self, years: list[int] | None = None, force: bool = False) -> List[Dict[str, Any]]:
        key = "draft_picks_all" if years is None else f"draft_picks_{'_'.join(map(str, years))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(
                ("load_draft_picks", "import_draft_picks", "read_draft_picks"),
                years=years,
            )

        return self._load_cached_or_call(key, load, force)

    def rosters(self, seasons: list[int], force: bool = False) -> List[Dict[str, Any]]:
        key = f"rosters_{'_'.join(map(str, seasons))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(("load_rosters", "import_rosters", "read_rosters"), seasons=seasons)

        return self._load_cached_or_call(key, load, force)

    def player_stats(self, seasons: list[int], force: bool = False) -> List[Dict[str, Any]]:
        key = f"player_stats_{'_'.join(map(str, seasons))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(
                ("load_player_stats", "import_weekly_data", "read_player_stats"),
                seasons=seasons,
            )

        return self._load_cached_or_call(key, load, force)

    def seasonal_rosters(self, seasons: list[int], force: bool = False) -> List[Dict[str, Any]]:
        key = f"seasonal_rosters_{'_'.join(map(str, seasons))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(
                (
                    "load_rosters",
                    "load_rosters_weekly",
                    "load_seasonal_rosters",
                    "import_rosters",
                    "import_weekly_rosters",
                    "read_rosters",
                ),
                seasons=seasons,
            )

        return self._load_cached_or_call(key, load, force)

    def weekly_rosters(self, seasons: list[int], force: bool = False) -> List[Dict[str, Any]]:
        key = f"weekly_rosters_{'_'.join(map(str, seasons))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(
                ("load_rosters_weekly", "import_weekly_rosters", "read_rosters_weekly"),
                seasons=seasons,
            )

        return self._load_cached_or_call(key, load, force)

    def players(self, force: bool = False) -> List[Dict[str, Any]]:
        key = "players"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(("load_players", "import_players", "read_players"))

        return self._load_cached_or_call(key, load, force)

    def pfr_advstats(
        self,
        seasons: list[int],
        stat_type: str,
        summary_level: str = "season",
        force: bool = False,
    ) -> List[Dict[str, Any]]:
        key = f"pfr_advstats_{stat_type}_{summary_level}_{'_'.join(map(str, seasons))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(
                ("load_pfr_advstats", "import_pfr_advstats", "read_pfr_advstats"),
                seasons=seasons,
                stat_type=stat_type,
                summary_level=summary_level,
            )

        return self._load_cached_or_call(key, load, force)

    def combine(self, years: list[int] | None = None, force: bool = False) -> List[Dict[str, Any]]:
        key = "combine_all" if years is None else f"combine_{'_'.join(map(str, years))}"

        def load() -> List[Dict[str, Any]]:
            return self._nflreadpy_call(("load_combine", "import_combine", "read_combine"), years=years)

        try:
            return self._load_cached_or_call(key, load, force)
        except Exception:
            return []

def load_career_summaries(*_args: Any, **_kwargs: Any) -> List[Dict[str, Any]]:
    return NFLVerseClient().player_stats(*_args, **_kwargs)
