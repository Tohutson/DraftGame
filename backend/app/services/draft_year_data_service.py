import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.core.config import get_settings
from app.data_pipeline.build_nfl_career_stats import build_career_payload, normalize_name, normalize_position
from app.data_sources.cfbd_client import CFBDClient, MissingCFBDAPIKey
from app.data_sources.nflverse_client import MissingNFLReadPy, NFLVerseClient
from app.database import connect, dumps, init_db, loads, session
from app.team_abbreviations import normalize_team_abbr


TEAM_NAMES = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB": "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "LV": "Las Vegas Raiders",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE": "New England Patriots",
    "NO": "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SEA": "Seattle Seahawks",
    "SF": "San Francisco 49ers",
    "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WSH": "Washington Commanders",
}

FIRST_NAMES = [
    "Mason",
    "Carter",
    "Wesley",
    "Darius",
    "Elliot",
    "Marcus",
    "Nolan",
    "Trevor",
    "Malik",
    "Damon",
    "Spencer",
    "Calvin",
]

LAST_NAMES = [
    "Brooks",
    "Hayes",
    "Porter",
    "Sullivan",
    "Bennett",
    "Reed",
    "Coleman",
    "Foster",
    "Warren",
    "Griffin",
    "Hampton",
    "Lawson",
]

POSITION_IMPORTANCE = {
    "QB": 1.4,
    "OT": 1.15,
    "EDGE": 1.15,
    "CB": 1.1,
    "WR": 1.0,
    "DL": 0.95,
    "DT": 0.95,
    "IOL": 0.85,
    "S": 0.8,
    "LB": 0.75,
    "TE": 0.7,
    "RB": 0.6,
    "K": 0.25,
    "P": 0.25,
}

TARGET_DEPTH = {
    "QB": 2,
    "RB": 3,
    "WR": 5,
    "TE": 3,
    "OT": 3,
    "IOL": 4,
    "EDGE": 4,
    "DL": 4,
    "DT": 4,
    "LB": 4,
    "CB": 5,
    "S": 4,
    "K": 1,
    "P": 1,
}


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _first(row: dict[str, Any], *fields: str, default: Any = None) -> Any:
    for field in fields:
        value = row.get(field)
        if value not in (None, "", "NA", "N/A"):
            return value
    return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _name(row: dict[str, Any]) -> str:
    return str(_first(row, "player_name", "pfr_player_name", "name", "full_name", "display_name", default="")).strip()


def _player_id(row: dict[str, Any]) -> str:
    value = _first(row, "player_id", "gsis_id", "nfl_id", "pfr_id", "cfb_id", "player_name", "pfr_player_name", "name")
    return str(value or _name(row))


def _fake_name(real_name: str, draft_year: int, rank: int) -> str:
    digest = hashlib.sha256(f"{draft_year}:{rank}:{real_name}".encode("utf-8")).hexdigest()
    first = FIRST_NAMES[int(digest[:2], 16) % len(FIRST_NAMES)]
    last = LAST_NAMES[int(digest[2:4], 16) % len(LAST_NAMES)]
    return f"{first} {last}"


def _height(row: dict[str, Any]) -> float | None:
    value = _first(row, "height", "height_in", "height_inches")
    if isinstance(value, str) and "-" in value:
        feet, inches = value.split("-", 1)
        return _int(feet) * 12 + _int(inches)
    return _float(value)


def _draft_pick(row: dict[str, Any]) -> int:
    return _int(_first(row, "overall", "pick", "overall_pick", "draft_pick", "selection"))


def _draft_round(row: dict[str, Any]) -> int:
    return _int(_first(row, "round", "draft_round"), 1)


def _pick_in_round(row: dict[str, Any]) -> int:
    return _int(_first(row, "pick_in_round", "round_pick", "pick"), _draft_pick(row))


def _draft_team(row: dict[str, Any]) -> str:
    return normalize_team_abbr(_first(row, "team", "team_abbr", "draft_team", "club", default=""))


def _college(row: dict[str, Any]) -> str:
    return str(_first(row, "college", "college_team", "school", "team", "cfb_team", default="Unknown"))


def _conference_for(college_team: str, teams: list[dict[str, Any]]) -> str | None:
    target = normalize_name(college_team)
    for team in teams:
        if normalize_name(team.get("school") or team.get("team") or team.get("name")) == target:
            return team.get("conference")
    return None


def _college_stats_for(real_name: str, college_team: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    name_key = normalize_name(real_name)
    team_key = normalize_name(college_team)
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        row_name = normalize_name(row.get("player") or row.get("playerName") or row.get("name"))
        row_team = normalize_name(row.get("team") or row.get("school"))
        if row_name != name_key:
            continue
        if team_key and row_team and row_team != team_key:
            continue
        stat_name = str(row.get("statName") or row.get("stat") or row.get("category") or "").lower()
        value = _float(row.get("stat") if "stat" not in row else row.get("stat"))
        value = value if value is not None else _float(row.get("value"))
        if stat_name and value is not None:
            totals[stat_name] += value
    return dict(totals)


class ValidationService:
    REAL_SOURCES = {"nflverse", "cfbd", "computed", "partial_nflverse", "partial"}

    def validate_draft_year(self, draft_year: int) -> dict[str, Any]:
        with connect() as conn:
            counts = {
                "prospects": conn.execute("SELECT COUNT(*) FROM prospects WHERE draft_year = ?", (draft_year,)).fetchone()[0],
                "draft_results": conn.execute("SELECT COUNT(*) FROM nfl_draft_results WHERE draft_year = ?", (draft_year,)).fetchone()[0],
                "career_stats": conn.execute("SELECT COUNT(*) FROM nfl_career_stats WHERE draft_year = ?", (draft_year,)).fetchone()[0],
                "team_needs": conn.execute("SELECT COUNT(*) FROM team_needs WHERE draft_year = ?", (draft_year,)).fetchone()[0],
            }
            source_rows = conn.execute(
                """
                SELECT source FROM prospects WHERE draft_year = ?
                UNION ALL SELECT source FROM team_needs WHERE draft_year = ?
                UNION ALL SELECT source FROM nfl_draft_results WHERE draft_year = ?
                UNION ALL SELECT source FROM nfl_career_stats WHERE draft_year = ?
                UNION ALL SELECT source FROM prospect_college_stats
                    WHERE prospect_id IN (SELECT id FROM prospects WHERE draft_year = ?)
                """,
                (draft_year, draft_year, draft_year, draft_year, draft_year),
            ).fetchall()
        source_counts = dict(Counter(row["source"] for row in source_rows))
        has_sample = any("sample" in source or "fallback" in source for source in source_counts)
        errors = []
        if counts["prospects"] == 0:
            errors.append("no prospects stored")
        if counts["draft_results"] < counts["prospects"]:
            errors.append("missing draft result rows")
        if has_sample and any(source in self.REAL_SOURCES for source in source_counts):
            errors.append("mixed real and sample/fallback sources")
        status = "complete"
        if errors:
            status = "partial" if counts["prospects"] and not has_sample else "failed"
        elif any(source.startswith("partial") for source in source_counts):
            status = "partial"
        return {
            "valid": status in {"complete", "partial"},
            "status": status,
            "counts": counts,
            "source_counts": source_counts,
            "errors": errors,
        }


class DraftYearDataService:
    def __init__(
        self,
        nflverse: NFLVerseClient | None = None,
        cfbd: CFBDClient | None = None,
        validation: ValidationService | None = None,
    ):
        init_db()
        self.nflverse = nflverse or NFLVerseClient()
        self.cfbd = cfbd or CFBDClient()
        self.validation = validation or ValidationService()

    def list_draft_years(self) -> list[dict[str, Any]]:
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
        return [self._build_row(row) for row in rows]

    def build_status(self, draft_year: int) -> dict[str, Any]:
        init_db()
        with connect() as conn:
            row = conn.execute(
                "SELECT * FROM data_builds WHERE draft_year = ? ORDER BY id DESC LIMIT 1",
                (draft_year,),
            ).fetchone()
        if not row:
            return {
                "draft_year": draft_year,
                "status": "missing",
                "cfbd_configured": bool(get_settings().cfbd_api_key),
            }
        payload = self._build_row(row)
        payload["cfbd_configured"] = bool(get_settings().cfbd_api_key)
        return payload

    def ensure_draft_year_ready(
        self, draft_year: int, through_season: int | None = None, force: bool = False
    ) -> dict[str, Any]:
        through = through_season or datetime.utcnow().year - 1
        if not force:
            status = self.build_status(draft_year)
            if status.get("status") in {"complete", "partial"} and self._has_game_data(draft_year):
                return status
        return self.build_draft_year(draft_year, through, force)

    def build_draft_year(self, draft_year: int, through_season: int, force: bool = False) -> dict[str, Any]:
        init_db()
        build_id = self._create_build(draft_year, through_season)
        try:
            if force:
                self._delete_year(draft_year)

            draft_rows = self.nflverse.draft_picks([draft_year], force=force)
            if not draft_rows:
                raise RuntimeError(f"nflreadpy returned no draft picks for {draft_year}")

            roster_rows = self.nflverse.rosters([draft_year - 1], force=force)
            try:
                combine_rows = self.nflverse.combine([draft_year], force=force)
            except Exception:
                combine_rows = []
            cfbd_status, college_stat_rows, college_team_rows = self._fetch_cfbd(draft_year, force)

            prospects = self._build_prospects(draft_year, draft_rows, combine_rows, college_team_rows)
            self._store_teams(draft_year - 1, prospects)
            self._store_rosters_and_needs(draft_year, draft_year - 1, roster_rows)
            self._store_prospects(draft_year, prospects, college_stat_rows, cfbd_status)
            self._store_career_stats(draft_year, through_season, prospects, force)

            validation = self.validation.validate_draft_year(draft_year)
            status = validation["status"]
            source_summary = {
                "nflverse": {
                    "draft_picks": len(draft_rows),
                    "rosters": len(roster_rows),
                    "combine": len(combine_rows),
                },
                "cfbd": {"status": cfbd_status, "college_stats": len(college_stat_rows), "teams": len(college_team_rows)},
            }
            self._finish_build(build_id, status, source_summary, validation)
            return self.build_status(draft_year)
        except MissingNFLReadPy as exc:
            self._fail_build(build_id, f"missing nflreadpy: {exc}")
            raise
        except Exception as exc:
            self._fail_build(build_id, str(exc))
            raise

    def _fetch_cfbd(self, draft_year: int, force: bool) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
        if not self.cfbd.available:
            return "skipped_missing_api_key", [], []
        try:
            stats = self.cfbd.get(
                "/stats/player/season",
                {"year": draft_year - 1},
                f"player_season_stats_{draft_year - 1}",
                force=force,
            )
            teams = self.cfbd.teams(draft_year - 1)
            return "fetched", list(stats or []), list(teams or [])
        except MissingCFBDAPIKey:
            return "skipped_missing_api_key", [], []
        except Exception as exc:
            return f"partial_error: {exc}", [], []

    def _build_prospects(
        self,
        draft_year: int,
        draft_rows: list[dict[str, Any]],
        combine_rows: list[dict[str, Any]],
        college_team_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        combine_by_name = {normalize_name(_name(row)): row for row in combine_rows if _name(row)}
        prospects = []
        for row in sorted(draft_rows, key=_draft_pick):
            pick = _draft_pick(row)
            if not pick:
                continue
            real_name = _name(row)
            if not real_name:
                continue
            combine = combine_by_name.get(normalize_name(real_name), {})
            position = normalize_position(_first(row, "position", "pos", "draft_position", default="UNK"))
            college_team = _college(row)
            height = _height(combine) or _height(row)
            weight = _float(_first(combine, "weight", "weight_lbs")) or _float(_first(row, "weight", "weight_lbs"))
            prospect = {
                "hidden_id": f"{draft_year}-{pick}",
                "real_player_id": _player_id(row),
                "real_name": real_name,
                "fake_name": _fake_name(real_name, draft_year, pick),
                "draft_year": draft_year,
                "rank": pick,
                "position": position,
                "position_group": position,
                "college_team": college_team,
                "conference": _conference_for(college_team, college_team_rows),
                "height": height,
                "weight": weight,
                "combine_summary": self._combine_summary(combine),
                "actual_draft": {
                    "year": draft_year,
                    "round": _draft_round(row),
                    "pick": _pick_in_round(row),
                    "overall": pick,
                    "team": _draft_team(row),
                },
                "source": "nflverse",
                "data_quality": "Draft pick loaded from nflreadpy/nflverse.",
            }
            prospects.append(prospect)
        return prospects

    def _combine_summary(self, row: dict[str, Any]) -> str | None:
        if not row:
            return None
        parts = []
        for label, field in (("40", "forty"), ("bench", "bench"), ("vertical", "vertical"), ("broad", "broad_jump")):
            value = _first(row, field, label)
            if value not in (None, "", "NA"):
                parts.append(f"{label}: {value}")
        return ", ".join(parts) or None

    def _store_teams(self, season: int, prospects: list[dict[str, Any]]) -> None:
        teams = sorted({_draft_team({"team": p["actual_draft"]["team"]}) for p in prospects if p["actual_draft"].get("team")})
        with session() as conn:
            for team in teams:
                conn.execute(
                    """
                    INSERT INTO teams(season, team_abbr, team_name, conference, division)
                    VALUES (?, ?, ?, NULL, NULL)
                    ON CONFLICT(season, team_abbr) DO UPDATE SET team_name = excluded.team_name
                    """,
                    (season, team, TEAM_NAMES.get(team, team)),
                )

    def _store_rosters_and_needs(self, draft_year: int, season: int, roster_rows: list[dict[str, Any]]) -> None:
        grouped: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"position_counts": Counter(), "position_groups": defaultdict(list), "data_source": "nflverse"}
        )
        roster_values = []
        for row in roster_rows:
            team = normalize_team_abbr(_first(row, "team", "recent_team", "club", "team_abbr", default=""))
            position = normalize_position(_first(row, "position", "pos", default=""))
            if not team or not position:
                continue
            player = {
                "player_id": _player_id(row),
                "player_name": _name(row),
                "position": position,
                "age": _float(row.get("age")),
                "years_exp": _float(_first(row, "years_exp", "experience", "rookie_year")),
                "production_score": 0,
            }
            grouped[team]["position_counts"][position] += 1
            grouped[team]["position_groups"][position].append(player)
            roster_values.append(
                (
                    draft_year,
                    season,
                    team,
                    player["player_name"],
                    player["player_id"],
                    position,
                    position,
                    player["age"],
                    player["years_exp"],
                    "nflverse",
                    dumps(row),
                )
            )
        with session() as conn:
            conn.execute("DELETE FROM team_rosters WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM team_needs WHERE draft_year = ?", (draft_year,))
            conn.executemany(
                """
                INSERT INTO team_rosters(
                    draft_year, season, team_abbr, player_name, player_id, position,
                    position_group, age, experience, source, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                roster_values,
            )
            for team, payload in grouped.items():
                payload["data_quality"] = "Roster snapshot loaded from nflreadpy/nflverse."
                needs = self._score_team_needs(dict(payload["position_counts"]), payload["data_quality"])
                for index, need in enumerate(needs, start=1):
                    conn.execute(
                        """
                        INSERT INTO team_needs(
                            draft_year, team_abbr, position_group, need_score, rank,
                            reason, source, data_quality
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            draft_year,
                            team,
                            need["position"],
                            need["need_score"],
                            index,
                            need.get("reason"),
                            "computed",
                            need.get("data_quality"),
                        ),
                    )

    def _store_prospects(
        self,
        draft_year: int,
        prospects: list[dict[str, Any]],
        college_stat_rows: list[dict[str, Any]],
        cfbd_status: str,
    ) -> None:
        with session() as conn:
            prospect_ids = [
                row["id"]
                for row in conn.execute("SELECT id FROM prospects WHERE draft_year = ?", (draft_year,)).fetchall()
            ]
            if prospect_ids:
                conn.executemany("DELETE FROM prospect_college_stats WHERE prospect_id = ?", [(pid,) for pid in prospect_ids])
            conn.execute("DELETE FROM nfl_draft_results WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM nfl_career_stats WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM prospects WHERE draft_year = ?", (draft_year,))
            for prospect in prospects:
                cursor = conn.execute(
                    """
                    INSERT INTO prospects(
                        draft_year, hidden_player_id, real_player_id, real_name, fake_name,
                        rank, position, position_group, college_team, conference, height,
                        weight, combine_summary, source, data_quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        draft_year,
                        prospect["hidden_id"],
                        prospect["real_player_id"],
                        prospect["real_name"],
                        prospect["fake_name"],
                        prospect["rank"],
                        prospect["position"],
                        prospect["position_group"],
                        prospect.get("college_team"),
                        prospect.get("conference"),
                        prospect.get("height"),
                        prospect.get("weight"),
                        prospect.get("combine_summary"),
                        "nflverse",
                        prospect["data_quality"],
                    ),
                )

                prospect_id = cursor.lastrowid
                stats = _college_stats_for(prospect["real_name"], prospect.get("college_team") or "", college_stat_rows)
                stat_source = "cfbd" if stats else ("partial" if cfbd_status != "fetched" else "cfbd")
                stat_quality = "College stats fetched from CollegeFootballData." if stats else f"No matched CFBD stats ({cfbd_status})."
                conn.execute(
                    """
                    INSERT INTO prospect_college_stats(
                        prospect_id, season, stat_type, stats_json, source, data_quality
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (prospect_id, draft_year - 1, "season", dumps(stats), stat_source, stat_quality),
                )
                draft = prospect["actual_draft"]
                conn.execute(
                    """
                    INSERT INTO nfl_draft_results(
                        prospect_id, draft_year, actual_round, actual_pick, actual_team, source
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (prospect_id, draft_year, draft["round"], draft["overall"], draft["team"], "nflverse"),
                )

    def _score_team_needs(self, counts: dict[str, int], data_quality: str) -> list[dict[str, Any]]:
        scored = []
        normalized = {normalize_position(position): int(count) for position, count in counts.items()}
        for position, target in TARGET_DEPTH.items():
            depth = normalized.get(position, 0)
            lack_of_depth = max(0, target - depth)
            score = round(POSITION_IMPORTANCE[position] * lack_of_depth, 3)
            if score <= 0:
                score = round(POSITION_IMPORTANCE[position] * 0.1, 3)
            scored.append(
                {
                    "position": position,
                    "need_score": score,
                    "reason": f"{position} depth {depth}/{target}",
                    "data_quality": data_quality,
                }
            )
        return sorted(scored, key=lambda item: item["need_score"], reverse=True)[:5]

    def _store_career_stats(
        self, draft_year: int, through_season: int, prospects: list[dict[str, Any]], force: bool
    ) -> None:
        seasons = list(range(draft_year, through_season + 1))
        stat_rows = self.nflverse.player_stats(seasons, force=force)
        roster_rows = []
        for loader in (self.nflverse.seasonal_rosters, self.nflverse.weekly_rosters):
            try:
                roster_rows.extend(loader(seasons, force=force))
            except Exception:
                continue
        payload = build_career_payload(draft_year, through_season, prospects, stat_rows, roster_rows)
        with session() as conn:
            rows = conn.execute(
                "SELECT id, real_player_id FROM prospects WHERE draft_year = ?", (draft_year,)
            ).fetchall()
            ids_by_real = {str(row["real_player_id"]): row["id"] for row in rows}
            for real_id, career in payload["players"].items():
                prospect_id = ids_by_real.get(str(real_id))
                if not prospect_id:
                    continue
                summary = career.get("career_summary") or {}
                conn.execute(
                    """
                    INSERT INTO nfl_career_stats(
                        prospect_id, draft_year, through_season, seasons, games, starts,
                        stats_json, career_value, outcome_label, summary, source, data_quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        prospect_id,
                        draft_year,
                        through_season,
                        _int(summary.get("seasons")),
                        _int(summary.get("games")),
                        _int(summary.get("starts")),
                        dumps(summary),
                        float(career.get("career_value") or 0),
                        career.get("outcome_label"),
                        json.dumps(summary, default=str),
                        career.get("career_data_source", payload.get("source", "partial")),
                        career.get("career_data_quality"),
                    ),
                )

    def _has_game_data(self, draft_year: int) -> bool:
        validation = self.validation.validate_draft_year(draft_year)
        return bool(validation["valid"] and validation["counts"]["prospects"])

    def _delete_year(self, draft_year: int) -> None:
        with session() as conn:
            prospect_ids = [row["id"] for row in conn.execute("SELECT id FROM prospects WHERE draft_year = ?", (draft_year,))]
            if prospect_ids:
                conn.executemany("DELETE FROM prospect_college_stats WHERE prospect_id = ?", [(pid,) for pid in prospect_ids])
            conn.execute("DELETE FROM nfl_draft_results WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM nfl_career_stats WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM prospects WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM team_rosters WHERE draft_year = ?", (draft_year,))
            conn.execute("DELETE FROM team_needs WHERE draft_year = ?", (draft_year,))

    def _create_build(self, draft_year: int, through_season: int) -> int:
        with session() as conn:
            cursor = conn.execute(
                """
                INSERT INTO data_builds(draft_year, through_season, status, source_summary_json, validation_summary_json)
                VALUES (?, ?, 'building', '{}', '{}')
                """,
                (draft_year, through_season),
            )
            return int(cursor.lastrowid)

    def _finish_build(
        self, build_id: int, status: str, source_summary: dict[str, Any], validation: dict[str, Any]
    ) -> None:
        with session() as conn:
            conn.execute(
                """
                UPDATE data_builds
                SET status = ?, completed_at = ?, error_message = NULL,
                    source_summary_json = ?, validation_summary_json = ?
                WHERE id = ?
                """,
                (status, _now(), dumps(source_summary), dumps(validation), build_id),
            )

    def _fail_build(self, build_id: int, error: str) -> None:
        with session() as conn:
            conn.execute(
                """
                UPDATE data_builds
                SET status = 'failed', completed_at = ?, error_message = ?,
                    validation_summary_json = ?
                WHERE id = ?
                """,
                (_now(), error, dumps({"valid": False, "errors": [error]}), build_id),
            )

    def _build_row(self, row: Any) -> dict[str, Any]:
        return {
            "id": row["id"],
            "draft_year": row["draft_year"],
            "through_season": row["through_season"],
            "status": row["status"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "error_message": row["error_message"],
            "source_summary": loads(row["source_summary_json"]),
            "validation_summary": loads(row["validation_summary_json"]),
        }


def get_draft_year_data_service() -> DraftYearDataService:
    return DraftYearDataService()
