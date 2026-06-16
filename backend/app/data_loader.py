from functools import lru_cache
from pathlib import Path
from typing import Any

from app.database import connect, init_db, loads
from app.services.draft_year_data_service import TEAM_NAMES
from app.team_abbreviations import normalize_team_abbr


DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATA_FILE = DATA_DIR / "sample_game_data.json"


class DataLoader:
    """DB-backed compatibility facade for the game service.

    The persistent SQLite database is the normal source of truth. The
    data_file argument remains only so older imports do not break; it is not
    read in normal mode.
    """

    def __init__(self, data_file: Path | None = None):
        self.data_file = data_file
        init_db()

    def teams(self, year: int | None = None) -> list[dict[str, Any]]:
        init_db()
        if year is None:
            with connect() as conn:
                rows = conn.execute(
                    """
                    SELECT t.*
                    FROM teams t
                    JOIN (
                        SELECT team_abbr, MAX(season) AS season FROM teams GROUP BY team_abbr
                    ) latest ON latest.team_abbr = t.team_abbr AND latest.season = t.season
                    ORDER BY t.team_abbr
                    """
                ).fetchall()
        else:
            with connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM teams WHERE season = ? ORDER BY team_abbr",
                    (int(year) - 1,),
                ).fetchall()
        teams = [self._team(row, year) for row in rows]
        if teams:
            return teams
        if year is None:
            return []
        team_ids = sorted(
            {
                normalize_team_abbr((p.get("actual_draft") or {}).get("team"))
                for p in self.prospects_for_year(year)
                if (p.get("actual_draft") or {}).get("team")
            }
        )
        if not team_ids:
            team_ids = sorted(TEAM_NAMES)
        return [
            {
                "id": team,
                "name": TEAM_NAMES.get(team, team),
                "abbreviation": team,
                "needs": self._needs_for_team(year, team),
                "need_details": self._need_details_for_team(year, team),
                "needs_source": "computed",
            }
            for team in team_ids
        ]

    def draft_years(self) -> list[int]:
        init_db()
        with connect() as conn:
            rows = conn.execute("SELECT DISTINCT draft_year FROM prospects ORDER BY draft_year").fetchall()
        return [int(row["draft_year"]) for row in rows]

    def build_statuses(self) -> list[dict[str, Any]]:
        init_db()
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT b.*
                FROM data_builds b
                JOIN (
                    SELECT draft_year, MAX(id) AS id FROM data_builds GROUP BY draft_year
                ) latest ON latest.id = b.id
                ORDER BY b.draft_year
                """
            ).fetchall()
        return [
            {
                "draft_year": row["draft_year"],
                "through_season": row["through_season"],
                "status": row["status"],
                "started_at": row["started_at"],
                "completed_at": row["completed_at"],
                "error_message": row["error_message"],
                "source_summary": loads(row["source_summary_json"]),
                "validation_summary": loads(row["validation_summary_json"]),
            }
            for row in rows
        ]

    def prospects_for_year(self, year: int) -> list[dict[str, Any]]:
        init_db()
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.*,
                    d.actual_round,
                    d.actual_pick,
                    d.actual_team,
                    c.through_season,
                    c.seasons,
                    c.games,
                    c.starts,
                    c.stats_json,
                    c.career_value,
                    c.outcome_label,
                    c.source AS career_source,
                    c.data_quality AS career_quality,
                    s.stats_json AS college_stats_json,
                    s.source AS college_stats_source,
                    s.data_quality AS college_stats_quality
                FROM prospects p
                LEFT JOIN nfl_draft_results d ON d.prospect_id = p.id
                LEFT JOIN nfl_career_stats c ON c.prospect_id = p.id
                    AND c.through_season = (
                        SELECT MAX(c2.through_season)
                        FROM nfl_career_stats c2
                        WHERE c2.prospect_id = p.id
                    )
                LEFT JOIN prospect_college_stats s ON s.prospect_id = p.id
                WHERE p.draft_year = ?
                ORDER BY p.rank
                """,
                (int(year),),
            ).fetchall()
        return [self._prospect(row) for row in rows]

    def team_by_id(self, team_id: str) -> dict[str, Any] | None:
        team_id = normalize_team_abbr(team_id)
        with connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM teams
                WHERE team_abbr = ?
                ORDER BY season DESC
                LIMIT 1
                """,
                (team_id,),
            ).fetchone()
        if row:
            return self._team(row, None)
        if team_id:
            return {
                "id": team_id,
                "name": TEAM_NAMES.get(team_id, team_id),
                "abbreviation": team_id,
                "needs": [],
                "need_details": [],
                "needs_source": "computed",
            }
        return None

    def prospect_by_hidden_id(self, hidden_id: str) -> dict[str, Any] | None:
        init_db()
        with connect() as conn:
            year = conn.execute(
                "SELECT draft_year FROM prospects WHERE hidden_player_id = ?",
                (hidden_id,),
            ).fetchone()
        if not year:
            return None
        return next((p for p in self.prospects_for_year(year["draft_year"]) if p["hidden_id"] == hidden_id), None)

    def _team(self, row: Any, year: int | None) -> dict[str, Any]:
        team_id = normalize_team_abbr(row["team_abbr"])
        draft_year = year or int(row["season"]) + 1
        return {
            "id": team_id,
            "name": row["team_name"] or TEAM_NAMES.get(team_id, team_id),
            "abbreviation": team_id,
            "conference": row["conference"],
            "division": row["division"],
            "needs": self._needs_for_team(draft_year, team_id),
            "need_details": self._need_details_for_team(draft_year, team_id),
            "needs_source": "computed",
        }

    def _needs_for_team(self, year: int | None, team_id: str) -> list[str]:
        if year is None:
            return []
        return [row["position_group"] for row in self._need_rows(year, team_id)]

    def _need_details_for_team(self, year: int | None, team_id: str) -> list[dict[str, Any]]:
        if year is None:
            return []
        return [
            {
                "position": row["position_group"],
                "need_score": row["need_score"],
                "score": row["need_score"],
                "rank": row["rank"],
                "reason": row["reason"],
                "data_source": row["source"],
                "data_quality": row["data_quality"],
            }
            for row in self._need_rows(year, team_id)
        ]

    def _need_rows(self, year: int, team_id: str) -> list[Any]:
        with connect() as conn:
            return conn.execute(
                """
                SELECT * FROM team_needs
                WHERE draft_year = ? AND team_abbr = ?
                ORDER BY rank
                """,
                (int(year), normalize_team_abbr(team_id)),
            ).fetchall()

    def _prospect(self, row: Any) -> dict[str, Any]:
        hidden_id = row["hidden_player_id"]
        career_summary = loads(row["stats_json"])
        if row["seasons"] is not None:
            career_summary.setdefault("seasons", row["seasons"])
        if row["games"] is not None:
            career_summary.setdefault("games", row["games"])
        if row["starts"]:
            career_summary.setdefault("starts", row["starts"])
        prospect = {
            "id": row["id"],
            "hidden_id": hidden_id,
            "hidden_player_id": hidden_id,
            "real_player_id": row["real_player_id"],
            "real_name": row["real_name"],
            "fake_name": row["fake_name"],
            "draft_year": row["draft_year"],
            "rank": row["rank"],
            "position": row["position"],
            "position_group": row["position_group"],
            "college_team": row["college_team"],
            "conference": row["conference"],
            "height": row["height"],
            "weight": row["weight"],
            "combine_summary": row["combine_summary"],
            "college_stats": loads(row["college_stats_json"]),
            "college_stats_source": row["college_stats_source"],
            "college_stats_quality": row["college_stats_quality"],
            "projected_round": row["actual_round"],
            "projected_pick": row["actual_pick"],
            "scouting_blurb": None,
            "scouting_report": [],
            "actual_draft": {
                "year": row["draft_year"],
                "round": row["actual_round"],
                "pick": row["actual_pick"],
                "overall": row["actual_pick"],
                "team": normalize_team_abbr(row["actual_team"]),
            },
            "career_summary": career_summary,
            "career_value": row["career_value"] or 0,
            "career_data_source": row["career_source"] or "partial",
            "career_data_quality": row["career_quality"] or "No career data available.",
            "outcome_label": row["outcome_label"],
            "reveal_blurb": (
                f"{row['real_name']} was selected {row['actual_pick']} overall by "
                f"{normalize_team_abbr(row['actual_team'])}."
            ),
        }
        return prospect


@lru_cache(maxsize=1)
def get_data_loader() -> DataLoader:
    return DataLoader()
