import argparse
import logging
import re
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Tuple

from app.data_pipeline.common import processed_path, prospects_for_year, write_json
from app.data_sources.nflverse_client import NFLVerseClient


LOGGER = logging.getLogger(__name__)

POSITION_ALIASES = {
    "C": "IOL",
    "G": "IOL",
    "OG": "IOL",
    "OL": "IOL",
    "T": "OT",
    "LT": "OT",
    "RT": "OT",
    "DE": "EDGE",
    "OLB": "LB",
    "ILB": "LB",
    "DB": "CB",
    "FS": "S",
    "SS": "S",
    "NT": "DT",
    "FB": "RB",
    "PK": "K",
}

POSITION_MATCH_GROUPS = {
    "QB": {"QB"},
    "RB": {"RB", "FB"},
    "WR": {"WR"},
    "TE": {"TE"},
    "OT": {"OT", "T", "LT", "RT", "OL"},
    "IOL": {"IOL", "C", "G", "OG", "OL"},
    "EDGE": {"EDGE", "DE", "OLB", "LB"},
    "DL": {"DL", "DT", "NT", "DE", "EDGE"},
    "DT": {"DT", "NT", "DL"},
    "LB": {"LB", "ILB", "OLB", "EDGE", "DE"},
    "CB": {"CB", "DB"},
    "S": {"S", "FS", "SS", "DB"},
    "K": {"K", "PK"},
    "P": {"P"},
}

SUM_FIELDS = {
    "games",
    "games_started",
    "starts",
    "passing_yards",
    "passing_tds",
    "passing_td",
    "interceptions",
    "passing_interceptions",
    "rushing_yards",
    "rushing_tds",
    "rushing_td",
    "receptions",
    "receiving_yards",
    "receiving_tds",
    "receiving_td",
    "carries",
    "sacks",
    "def_sacks",
    "tackles",
    "def_tackles",
    "solo_tackles",
    "assists",
    "def_interceptions",
    "forced_fumbles",
    "fg_made",
    "field_goals_made",
    "fg_att",
    "field_goals_attempted",
    "xp_made",
    "extra_points_made",
    "punts",
    "punt_yards",
}


def _number(value: Any) -> float:
    if value in (None, "", "NA", "N/A"):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: float) -> int:
    return int(round(value))


def normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", text)
    return re.sub(r"[^a-z0-9]", "", text)


def normalize_position(value: Any) -> str:
    position = str(value or "").upper()
    return POSITION_ALIASES.get(position, position)


def _player_id(row: Dict[str, Any]) -> str | None:
    for field in ("player_id", "gsis_id", "nfl_id", "esb_id", "pfr_id"):
        value = row.get(field)
        if value not in (None, "", "NA"):
            return str(value)
    return None


def _player_name(row: Dict[str, Any]) -> str:
    return str(
        row.get("player_display_name")
        or row.get("display_name")
        or row.get("full_name")
        or row.get("football_name")
        or row.get("player_name")
        or row.get("name")
        or ""
    )


def _stat(row: Dict[str, Any], *fields: str) -> float:
    return sum(_number(row.get(field)) for field in fields)


def _aggregate_stats(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    players: Dict[str, Dict[str, Any]] = {}
    weekly_rows: Dict[str, int] = defaultdict(int)
    for row in rows:
        player_id = _player_id(row)
        if not player_id:
            continue
        player = players.setdefault(
            player_id,
            {
                "player_id": player_id,
                "player_name": _player_name(row),
                "position": normalize_position(row.get("position") or row.get("pos")),
                "seasons": set(),
                "totals": defaultdict(float),
            },
        )
        if not player["player_name"]:
            player["player_name"] = _player_name(row)
        if not player["position"]:
            player["position"] = normalize_position(row.get("position") or row.get("pos"))
        season = row.get("season")
        if season not in (None, "", "NA"):
            player["seasons"].add(int(float(season)))
        if row.get("week") not in (None, "", "NA"):
            weekly_rows[player_id] += 1
        for field in SUM_FIELDS:
            player["totals"][field] += _number(row.get(field))

    for player_id, player in players.items():
        totals = player["totals"]
        if not totals.get("games") and weekly_rows.get(player_id):
            totals["games"] = weekly_rows[player_id]
        player["seasons"] = sorted(player["seasons"])
        player["totals"] = dict(totals)
    return players


def _aggregate_roster_presence(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    players: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        player_id = _player_id(row)
        if not player_id:
            continue
        player = players.setdefault(
            player_id,
            {
                "player_id": player_id,
                "player_name": _player_name(row),
                "position": normalize_position(row.get("position") or row.get("pos")),
                "seasons": set(),
                "games": 0.0,
                "starts": 0.0,
            },
        )
        season = row.get("season")
        if season not in (None, "", "NA"):
            player["seasons"].add(int(float(season)))
        player["games"] += _stat(row, "games", "games_played")
        player["starts"] += _stat(row, "starts", "games_started")
    for player in players.values():
        player["seasons"] = sorted(player["seasons"])
    return players


def _position_match_keys(position: Any) -> set[str]:
    normalized = normalize_position(position)
    return {normalize_position(item) for item in POSITION_MATCH_GROUPS.get(normalized, {normalized})}


def _name_position_index(players: Dict[str, Dict[str, Any]]) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
    index: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for player in players.values():
        name = normalize_name(player.get("player_name"))
        if not name:
            continue
        for position in _position_match_keys(player.get("position")):
            index[(name, position)].append(player)
    return index


def _match_player(
    prospect: Dict[str, Any],
    stat_players: Dict[str, Dict[str, Any]],
    roster_players: Dict[str, Dict[str, Any]],
    stat_name_index: Dict[Tuple[str, str], List[Dict[str, Any]]],
    roster_name_index: Dict[Tuple[str, str], List[Dict[str, Any]]],
) -> Tuple[Dict[str, Any] | None, Dict[str, Any] | None, str, str | None]:
    real_id = str(prospect.get("real_player_id") or "")
    if real_id and (real_id in stat_players or real_id in roster_players):
        return stat_players.get(real_id), roster_players.get(real_id), "id", None

    name = normalize_name(prospect.get("real_name"))
    positions = _position_match_keys(prospect.get("position"))
    stat_matches = []
    roster_matches = []
    for position in positions:
        stat_matches.extend(stat_name_index.get((name, position), []))
        roster_matches.extend(roster_name_index.get((name, position), []))
    stat_matches = list({match["player_id"]: match for match in stat_matches}.values())
    roster_matches = list({match["player_id"]: match for match in roster_matches}.values())
    if len(stat_matches) == 1 or len(roster_matches) == 1:
        warning = f"{prospect.get('real_name')} matched by normalized name/position, not stable id"
        return (
            stat_matches[0] if len(stat_matches) == 1 else None,
            roster_matches[0] if len(roster_matches) == 1 else None,
            "name_position",
            warning,
        )
    if len(stat_matches) > 1 or len(roster_matches) > 1:
        return None, None, "unmatched", f"{prospect.get('real_name')} had multiple normalized name matches"
    return None, None, "unmatched", None


def _summary_for(position: str, seasons: List[int], totals: Dict[str, float], roster: Dict[str, Any] | None) -> Dict[str, int]:
    position = normalize_position(position)
    games = _int(totals.get("games") or (roster or {}).get("games") or 0)
    starts = _int(totals.get("starts") or totals.get("games_started") or (roster or {}).get("starts") or 0)
    base = {"seasons": len(seasons), "games": games}
    if starts:
        base["starts"] = starts
    if position == "QB":
        return {
            **base,
            "passing_yards": _int(totals.get("passing_yards", 0)),
            "passing_td": _int(totals.get("passing_tds", 0) or totals.get("passing_td", 0)),
            "interceptions": _int(totals.get("interceptions", 0) or totals.get("passing_interceptions", 0)),
            "rushing_yards": _int(totals.get("rushing_yards", 0)),
            "rushing_td": _int(totals.get("rushing_tds", 0) or totals.get("rushing_td", 0)),
        }
    if position == "RB":
        return {
            **base,
            "rushing_yards": _int(totals.get("rushing_yards", 0)),
            "rushing_td": _int(totals.get("rushing_tds", 0) or totals.get("rushing_td", 0)),
            "receptions": _int(totals.get("receptions", 0)),
            "receiving_yards": _int(totals.get("receiving_yards", 0)),
            "receiving_td": _int(totals.get("receiving_tds", 0) or totals.get("receiving_td", 0)),
        }
    if position in {"WR", "TE"}:
        return {
            **base,
            "receptions": _int(totals.get("receptions", 0)),
            "receiving_yards": _int(totals.get("receiving_yards", 0)),
            "receiving_td": _int(totals.get("receiving_tds", 0) or totals.get("receiving_td", 0)),
        }
    if position in {"OT", "IOL"}:
        return base
    if position == "K":
        return {
            **base,
            "field_goals_made": _int(totals.get("fg_made", 0) or totals.get("field_goals_made", 0)),
            "field_goals_attempted": _int(totals.get("fg_att", 0) or totals.get("field_goals_attempted", 0)),
            "extra_points_made": _int(totals.get("xp_made", 0) or totals.get("extra_points_made", 0)),
        }
    if position == "P":
        return {
            **base,
            "punts": _int(totals.get("punts", 0)),
            "punt_yards": _int(totals.get("punt_yards", 0)),
        }
    return {
        **base,
        "tackles": _int(totals.get("tackles", 0) or totals.get("def_tackles", 0) or totals.get("solo_tackles", 0) + totals.get("assists", 0)),
        "sacks": _int(totals.get("sacks", 0) or totals.get("def_sacks", 0)),
        "interceptions": _int(totals.get("def_interceptions", 0) or totals.get("interceptions", 0)),
        "forced_fumbles": _int(totals.get("forced_fumbles", 0)),
    }


def _career_value(position: str, summary: Dict[str, int]) -> float:
    position = normalize_position(position)
    games = summary.get("games", 0)
    starts = summary.get("starts", 0)
    value = games * 0.25 + starts * 0.35 + summary.get("seasons", 0) * 1.5
    if position == "QB":
        value += summary.get("passing_yards", 0) / 400 + summary.get("passing_td", 0) * 1.8
        value += summary.get("rushing_yards", 0) / 250 + summary.get("rushing_td", 0) * 1.2
        value -= summary.get("interceptions", 0) * 1.0
    elif position == "RB":
        value += summary.get("rushing_yards", 0) / 120 + summary.get("receiving_yards", 0) / 160
        value += (summary.get("rushing_td", 0) + summary.get("receiving_td", 0)) * 1.0
        value += summary.get("receptions", 0) / 18
    elif position in {"WR", "TE"}:
        value += summary.get("receiving_yards", 0) / 130 + summary.get("receiving_td", 0) * 1.2
        value += summary.get("receptions", 0) / 15
    elif position in {"OT", "IOL"}:
        value += games * 0.45 + starts * 0.55
    elif position == "K":
        value += summary.get("field_goals_made", 0) * 0.35 + summary.get("extra_points_made", 0) * 0.06
    elif position == "P":
        value += summary.get("punts", 0) * 0.04 + summary.get("punt_yards", 0) / 1200
    else:
        value += summary.get("tackles", 0) / 14 + summary.get("sacks", 0) * 2.5
        value += summary.get("interceptions", 0) * 3.0 + summary.get("forced_fumbles", 0) * 2.0
    return round(max(value, 0), 1)


def _outcome_label(value: float) -> str:
    if value >= 80:
        return "Star"
    if value >= 45:
        return "Starter"
    if value >= 18:
        return "Contributor"
    if value > 0:
        return "Reserve / Limited Production"
    return "Unknown / Insufficient Data"


def _fallback_entry(prospect: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {
        "hidden_id": prospect.get("hidden_id"),
        "real_player_id": prospect.get("real_player_id"),
        "real_name": prospect.get("real_name"),
        "position": prospect.get("position"),
        "career_summary": prospect.get("career_summary", {}),
        "career_value": prospect.get("career_value", 0),
        "outcome_label": prospect.get("outcome_label", "Unknown / Insufficient Data"),
        "career_data_source": "fallback_sample",
        "career_data_quality": reason,
        "match_method": "fallback_sample",
    }


def build_career_payload(
    draft_year: int,
    through_season: int,
    prospects: List[Dict[str, Any]],
    stat_rows: List[Dict[str, Any]],
    roster_rows: List[Dict[str, Any]],
    source: str = "nflverse",
) -> Dict[str, Any]:
    stat_players = _aggregate_stats(stat_rows)
    roster_players = _aggregate_roster_presence(roster_rows)
    stat_name_index = _name_position_index(stat_players)
    roster_name_index = _name_position_index(roster_players)
    players: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []

    for prospect in prospects:
        stat_player, roster_player, match_method, warning = _match_player(
            prospect, stat_players, roster_players, stat_name_index, roster_name_index
        )
        if warning:
            warnings.append(warning)
            LOGGER.warning(warning)
        if not stat_player and not roster_player:
            players[str(prospect["real_player_id"])] = _fallback_entry(
                prospect, "No nflverse stats or roster presence matched this drafted player; using marked sample fallback."
            )
            continue

        totals = dict((stat_player or {}).get("totals", {}))
        seasons = sorted(set((stat_player or {}).get("seasons", [])) | set((roster_player or {}).get("seasons", [])))
        summary = _summary_for(prospect["position"], seasons, totals, roster_player)
        has_box_stats = bool(stat_player and any(value for value in totals.values()))
        has_roster_presence = bool(roster_player)
        data_source = "nflverse" if has_box_stats else "partial_nflverse"
        quality = "Aggregated from nflverse player stats."
        if data_source == "partial_nflverse":
            quality = "Matched nflverse roster presence, but detailed position stats were unavailable."
        value = _career_value(prospect["position"], summary)
        players[str(prospect["real_player_id"])] = {
            "hidden_id": prospect.get("hidden_id"),
            "real_player_id": prospect.get("real_player_id"),
            "nflverse_player_id": (stat_player or roster_player or {}).get("player_id"),
            "real_name": prospect.get("real_name"),
            "position": prospect.get("position"),
            "career_summary": summary,
            "career_value": value,
            "outcome_label": _outcome_label(value),
            "career_data_source": data_source,
            "career_data_quality": quality,
            "match_method": match_method,
        }

    source_counts: Dict[str, int] = defaultdict(int)
    for player in players.values():
        source_counts[player.get("career_data_source", "unknown")] += 1
    if not players or source_counts.get("fallback_sample", 0) == len(players):
        payload_source = "fallback_sample"
    elif source_counts.get("nflverse", 0):
        payload_source = "nflverse"
    else:
        payload_source = "partial_nflverse"

    return {
        "draft_year": draft_year,
        "through_season": through_season,
        "source": payload_source,
        "source_counts": dict(source_counts),
        "players": players,
        "warnings": warnings[:200],
        "warning_count": len(warnings),
    }


def build_nfl_career_stats(draft_year: int, through_season: int | None = None, force: bool = False) -> Dict[str, Any]:
    through = through_season or 2025
    seasons = list(range(draft_year, through + 1))
    prospects = prospects_for_year(draft_year)
    nflverse = NFLVerseClient()
    try:
        stat_rows = nflverse.player_stats(seasons, force=force)
        roster_rows = []
        for loader_name, loader in (
            ("load_rosters", nflverse.seasonal_rosters),
            ("load_rosters_weekly", nflverse.weekly_rosters),
            ("load_players", lambda _seasons, force=False: nflverse.players(force=force)),
        ):
            try:
                loaded = loader(seasons, force=force)
                roster_rows.extend(loaded)
                LOGGER.info("Loaded %s rows from %s for career enrichment", len(loaded), loader_name)
            except Exception as exc:
                LOGGER.warning("nflverse %s load failed for career enrichment: %s", loader_name, exc)
        payload = build_career_payload(draft_year, through, prospects, stat_rows, roster_rows)
    except Exception as exc:
        LOGGER.warning("nflverse career stat load failed; writing marked sample fallback: %s", exc)
        players = {
            str(prospect["real_player_id"]): _fallback_entry(
                prospect, f"nflverse player stats unavailable: {exc}"
            )
            for prospect in prospects
        }
        payload = {
            "draft_year": draft_year,
            "through_season": through,
            "source": "fallback_sample",
            "players": players,
            "warnings": [f"nflverse player stats unavailable: {exc}"],
            "warning_count": 1,
        }

    path = write_json(processed_path(f"career_stats_{draft_year}_through_{through}.json"), payload)
    source_counts: Dict[str, int] = defaultdict(int)
    for player in payload["players"].values():
        source_counts[player.get("career_data_source", payload["source"])] += 1
    return {
        "path": str(path),
        "player_count": len(payload["players"]),
        "source": payload["source"],
        "source_counts": payload.get("source_counts", dict(source_counts)),
        "warning_count": payload.get("warning_count", 0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-year", type=int, required=True)
    parser.add_argument("--through-season", type=int, default=2025)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(build_nfl_career_stats(args.draft_year, args.through_season, args.force))


if __name__ == "__main__":
    main()
