import argparse
import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List

from app.data_pipeline.build_nfl_career_stats import normalize_position
from app.data_pipeline.common import processed_path, write_json
from app.data_loader import DataLoader
from app.data_sources.nflverse_client import NFLVerseClient
from app.team_abbreviations import normalize_team_abbr


LOGGER = logging.getLogger(__name__)


def _number(value: Any) -> float:
    if value in (None, "", "NA", "N/A"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _player_name(row: Dict[str, Any]) -> str:
    return str(row.get("player_name") or row.get("player_display_name") or row.get("display_name") or row.get("name") or "")


def _player_id(row: Dict[str, Any]) -> str:
    return str(row.get("player_id") or row.get("gsis_id") or row.get("nfl_id") or row.get("pfr_id") or _player_name(row))


def _team(row: Dict[str, Any]) -> str:
    return normalize_team_abbr(row.get("team") or row.get("recent_team") or row.get("club") or row.get("team_abbr"))


def _production_by_player(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    production: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        player_id = _player_id(row)
        production[player_id]["passing_yards"] += _number(row.get("passing_yards"))
        production[player_id]["passing_tds"] += _number(row.get("passing_tds") or row.get("passing_td"))
        production[player_id]["rushing_yards"] += _number(row.get("rushing_yards"))
        production[player_id]["rushing_tds"] += _number(row.get("rushing_tds") or row.get("rushing_td"))
        production[player_id]["receptions"] += _number(row.get("receptions"))
        production[player_id]["receiving_yards"] += _number(row.get("receiving_yards"))
        production[player_id]["receiving_tds"] += _number(row.get("receiving_tds") or row.get("receiving_td"))
        production[player_id]["sacks"] += _number(row.get("sacks") or row.get("def_sacks"))
        production[player_id]["tackles"] += _number(row.get("tackles") or row.get("def_tackles") or row.get("solo_tackles"))
        production[player_id]["interceptions"] += _number(row.get("def_interceptions") or row.get("interceptions"))
        production[player_id]["games"] += _number(row.get("games"))
        if row.get("week") not in (None, "", "NA") and not row.get("games"):
            production[player_id]["games"] += 1
    return {player_id: dict(values) for player_id, values in production.items()}


def _production_score(position: str, production: Dict[str, float]) -> float:
    position = normalize_position(position)
    if position == "QB":
        return production.get("passing_yards", 0) / 500 + production.get("passing_tds", 0) * 1.5
    if position == "RB":
        return production.get("rushing_yards", 0) / 150 + production.get("receiving_yards", 0) / 200
    if position in {"WR", "TE"}:
        return production.get("receiving_yards", 0) / 180 + production.get("receptions", 0) / 20
    if position in {"EDGE", "DL", "DT", "LB", "CB", "S"}:
        return production.get("tackles", 0) / 18 + production.get("sacks", 0) * 1.8 + production.get("interceptions", 0) * 2.0
    return production.get("games", 0) / 3


def _real_rosters(season: int, force: bool) -> Dict[str, Any]:
    nflverse = NFLVerseClient()
    rosters = nflverse.rosters([season], force=force)
    try:
        stats = nflverse.player_stats([season], force=force)
    except Exception as exc:
        LOGGER.warning("nflverse previous-season player stats unavailable for team needs: %s", exc)
        stats = []
    production = _production_by_player(stats)
    teams: Dict[str, Dict[str, Any]] = {}
    grouped: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    counts: Dict[str, Counter] = defaultdict(Counter)

    for row in rosters:
        team_id = _team(row)
        position = normalize_position(row.get("position") or row.get("pos"))
        if not team_id or not position:
            continue
        player_id = _player_id(row)
        player_production = production.get(player_id, {})
        counts[team_id][position] += 1
        grouped[team_id][position].append(
            {
                "player_id": player_id,
                "player_name": _player_name(row),
                "position": position,
                "age": row.get("age"),
                "years_exp": row.get("years_exp") or row.get("rookie_year"),
                "games": _number(row.get("games") or row.get("games_played") or player_production.get("games")),
                "starts": _number(row.get("starts") or row.get("games_started")),
                "production_score": round(_production_score(position, player_production), 3),
            }
        )

    for team_id, position_counts in counts.items():
        teams[team_id] = {
            "team_id": team_id,
            "season": season,
            "position_counts": dict(position_counts),
            "position_groups": grouped[team_id],
            "data_source": "nflverse",
            "data_quality": "Roster snapshot loaded from nflverse; previous-season production included when player stats matched.",
        }
    return {"source": "nflverse", "teams": teams}


def _fallback_rosters(season: int, reason: str) -> Dict[str, Any]:
    LOGGER.warning("Using marked fallback team rosters for %s: %s", season, reason)
    loader = DataLoader()
    draft_year = season + 1
    teams: Dict[str, Dict[str, Any]] = {}
    for team in loader.teams(draft_year):
        team_id = normalize_team_abbr(team["id"])
        counts = Counter(
            normalize_position(p["position"])
            for p in loader.prospects_for_year(draft_year)
            if normalize_team_abbr((p.get("actual_draft") or {}).get("team")) == team_id
        )
        teams[team_id] = {
            "team_id": team_id,
            "season": season,
            "position_counts": dict(counts),
            "position_groups": {},
            "data_source": "fallback",
            "data_quality": f"Fallback only: derived from next draft class because nflverse rosters were unavailable ({reason}).",
        }
    return {"source": "fallback", "teams": teams}


def build_team_rosters(season: int, force: bool = False) -> Dict[str, Any]:
    try:
        payload = _real_rosters(season, force)
        if not payload["teams"]:
            payload = _fallback_rosters(season, "nflverse returned no roster rows")
    except Exception as exc:
        payload = _fallback_rosters(season, str(exc))

    path = write_json(
        processed_path(f"team_rosters_{season}.json"),
        {"season": season, "source": payload["source"], "teams": payload["teams"]},
    )
    return {"path": str(path), "team_count": len(payload["teams"]), "source": payload["source"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(build_team_rosters(args.season, args.force))


if __name__ == "__main__":
    main()
