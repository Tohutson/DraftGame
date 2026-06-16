import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_cache_dir: Path
    cfbd_api_key: str | None
    default_draft_year: int
    default_random_seed: int
    enable_espn_fallback: bool
    database_url: str | None

    @property
    def raw_dir(self) -> Path:
        return self.data_cache_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_cache_dir / "processed"

    @property
    def sample_dir(self) -> Path:
        return self.data_cache_dir / "sample"

    @property
    def sqlite_db_path(self) -> Path:
        if self.database_url and self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", "", 1)).resolve()
        return self.data_cache_dir / "draft_game.db"


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def get_settings() -> Settings:
    default_data_dir = Path(__file__).resolve().parents[1] / "data"
    data_cache_dir = Path(os.getenv("DATA_CACHE_DIR", default_data_dir)).resolve()
    return Settings(
        data_cache_dir=data_cache_dir,
        cfbd_api_key=os.getenv("CFBD_API_KEY") or os.getenv("COLLEGE_FOOTBALL_DATA_API_KEY"),
        default_draft_year=int(os.getenv("DEFAULT_DRAFT_YEAR", "2018")),
        default_random_seed=int(os.getenv("DEFAULT_RANDOM_SEED", "42")),
        enable_espn_fallback=_bool_env("ENABLE_ESPN_FALLBACK", False),
        database_url=os.getenv("DATABASE_URL"),
    )


def ensure_data_dirs(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    for path in (settings.raw_dir, settings.processed_dir, settings.sample_dir, settings.sqlite_db_path.parent):
        path.mkdir(parents=True, exist_ok=True)
