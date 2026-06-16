import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.core.config import ensure_data_dirs, get_settings


def _json(value: Any) -> str:
    return json.dumps(value if value is not None else {}, default=str)


def _loads(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return {} if default is None else default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {} if default is None else default


def db_path() -> Path:
    settings = get_settings()
    ensure_data_dirs(settings)
    return settings.sqlite_db_path


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def session(path: Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS data_builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_year INTEGER NOT NULL,
    through_season INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    error_message TEXT,
    source_summary_json TEXT NOT NULL DEFAULT '{}',
    validation_summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_data_builds_year_status
ON data_builds(draft_year, status, started_at);

CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season INTEGER NOT NULL,
    team_abbr TEXT NOT NULL,
    team_name TEXT NOT NULL,
    conference TEXT,
    division TEXT,
    UNIQUE(season, team_abbr)
);

CREATE TABLE IF NOT EXISTS team_rosters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_year INTEGER NOT NULL,
    season INTEGER NOT NULL,
    team_abbr TEXT NOT NULL,
    player_name TEXT,
    player_id TEXT,
    position TEXT,
    position_group TEXT,
    age REAL,
    experience REAL,
    source TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_team_rosters_year_team
ON team_rosters(draft_year, team_abbr);

CREATE TABLE IF NOT EXISTS team_needs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_year INTEGER NOT NULL,
    team_abbr TEXT NOT NULL,
    position_group TEXT NOT NULL,
    need_score REAL NOT NULL,
    rank INTEGER NOT NULL,
    reason TEXT,
    source TEXT NOT NULL,
    data_quality TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_team_needs_unique
ON team_needs(draft_year, team_abbr, position_group);

CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    draft_year INTEGER NOT NULL,
    hidden_player_id TEXT NOT NULL UNIQUE,
    real_player_id TEXT,
    real_name TEXT NOT NULL,
    fake_name TEXT NOT NULL,
    rank INTEGER NOT NULL,
    position TEXT NOT NULL,
    position_group TEXT NOT NULL,
    college_team TEXT,
    conference TEXT,
    height REAL,
    weight REAL,
    combine_summary TEXT,
    source TEXT NOT NULL,
    data_quality TEXT
);

CREATE INDEX IF NOT EXISTS idx_prospects_year_rank
ON prospects(draft_year, rank);

CREATE TABLE IF NOT EXISTS prospect_college_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    season INTEGER,
    stat_type TEXT NOT NULL,
    stats_json TEXT NOT NULL DEFAULT '{}',
    source TEXT NOT NULL,
    data_quality TEXT
);

CREATE TABLE IF NOT EXISTS nfl_draft_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    draft_year INTEGER NOT NULL,
    actual_round INTEGER,
    actual_pick INTEGER,
    actual_team TEXT,
    source TEXT NOT NULL,
    UNIQUE(prospect_id, draft_year)
);

CREATE TABLE IF NOT EXISTS nfl_career_stats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prospect_id INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
    draft_year INTEGER NOT NULL,
    through_season INTEGER NOT NULL,
    seasons INTEGER NOT NULL DEFAULT 0,
    games INTEGER NOT NULL DEFAULT 0,
    starts INTEGER NOT NULL DEFAULT 0,
    stats_json TEXT NOT NULL DEFAULT '{}',
    career_value REAL NOT NULL DEFAULT 0,
    outcome_label TEXT,
    summary TEXT,
    source TEXT NOT NULL,
    data_quality TEXT,
    UNIQUE(prospect_id, draft_year, through_season)
);

CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    draft_year INTEGER NOT NULL,
    user_team TEXT NOT NULL,
    current_pick INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    seed INTEGER NOT NULL,
    rounds INTEGER NOT NULL,
    draft_order_json TEXT NOT NULL DEFAULT '[]',
    available_ids_json TEXT NOT NULL DEFAULT '[]',
    user_team_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS draft_picks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    pick_number INTEGER NOT NULL,
    round INTEGER NOT NULL,
    team_abbr TEXT NOT NULL,
    prospect_id INTEGER REFERENCES prospects(id),
    hidden_player_id TEXT,
    fake_name TEXT,
    position TEXT,
    college_team TEXT,
    made_by_user INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(game_id, pick_number)
);
"""


def init_db(path: Path | None = None) -> None:
    with session(path) as conn:
        conn.executescript(SCHEMA)


def table_counts(path: Path | None = None) -> dict[str, int]:
    init_db(path)
    tables = [
        "data_builds",
        "teams",
        "team_rosters",
        "team_needs",
        "prospects",
        "prospect_college_stats",
        "nfl_draft_results",
        "nfl_career_stats",
        "games",
        "draft_picks",
    ]
    with connect(path) as conn:
        return {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}


def dumps(value: Any) -> str:
    return _json(value)


def loads(value: Any, default: Any = None) -> Any:
    return _loads(value, default)
