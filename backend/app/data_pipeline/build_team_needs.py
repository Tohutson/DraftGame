import argparse
import json
import logging
from typing import Any, Dict, List

from app.data_pipeline.build_nfl_career_stats import normalize_position
from app.data_pipeline.build_team_rosters import build_team_rosters
from app.data_pipeline.common import processed_path, write_json


LOGGER = logging.getLogger(__name__)

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


def _load_rosters(season: int) -> Dict[str, Any]:
    path = processed_path(f"team_rosters_{season}.json")
    if not path.exists():
        build_team_rosters(season)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _position_players(team: Dict[str, Any], position: str) -> List[Dict[str, Any]]:
    groups = team.get("position_groups") or {}
    direct = groups.get(position) or []
    if direct:
        return direct
    if position == "DL":
        return (groups.get("DL") or []) + (groups.get("DT") or []) + (groups.get("EDGE") or [])
    return []


def _need_reason(position: str, depth: int, target: int, production: float, data_source: str) -> str:
    if data_source == "fallback":
        return f"Fallback estimate: {position} depth inferred from next draft class, not a real roster snapshot."
    parts = [f"{position} depth {depth}/{target}"]
    if production <= 1 and depth:
        parts.append("low matched previous-season production")
    if depth == 0:
        parts.append("no rostered players found in snapshot")
    return "; ".join(parts)


def score_team_needs(team: Dict[str, Any], roster_source: str) -> List[Dict[str, Any]]:
    counts = {normalize_position(position): int(count) for position, count in (team.get("position_counts") or {}).items()}
    team_source = team.get("data_source") or roster_source
    scored = []
    for position, target in TARGET_DEPTH.items():
        depth = int(counts.get(position, 0))
        players = _position_players(team, position)
        production = sum(float(player.get("production_score") or 0) for player in players)
        lack_of_depth = max(0, target - depth)
        production_gap = 0.0
        if team_source != "fallback":
            expected_production = max(1.0, target * POSITION_IMPORTANCE[position] * 1.2)
            production_gap = max(0.0, (expected_production - production) / expected_production)
        elif depth <= max(1, target // 2):
            production_gap = 1.0
        score = round(POSITION_IMPORTANCE[position] * (lack_of_depth + production_gap), 3)
        scored.append(
            {
                "position": position,
                "need_score": score,
                "score": score,
                "depth": depth,
                "target_depth": target,
                "recent_production_score": round(production, 3),
                "reason": _need_reason(position, depth, target, production, team_source),
                "data_source": "fallback" if team_source == "fallback" else "nflverse",
                "data_quality": team.get("data_quality") or (
                    "Fallback only; nflverse roster data unavailable."
                    if team_source == "fallback"
                    else "Derived from nflverse roster depth and matched previous-season production."
                ),
            }
        )
    return sorted(scored, key=lambda item: item["need_score"], reverse=True)[:5]


def build_team_needs(season: int) -> Dict[str, Any]:
    rosters = _load_rosters(season)
    roster_source = rosters.get("source", "unknown")
    if roster_source == "fallback":
        LOGGER.warning("Building marked fallback team needs for %s because roster source is fallback", season)
    needs: Dict[str, List[Dict[str, Any]]] = {}
    for team_id, team in rosters.get("teams", {}).items():
        needs[team_id] = score_team_needs(team, roster_source)
    payload = {"season": season, "source": "fallback" if roster_source == "fallback" else "nflverse", "teams": needs}
    path = write_json(processed_path(f"team_needs_{season}.json"), payload)
    source_counts: Dict[str, int] = {}
    for rows in needs.values():
        for row in rows:
            source = row.get("data_source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
    return {"path": str(path), "team_count": len(needs), "source": payload["source"], "source_counts": source_counts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    args = parser.parse_args()
    print(build_team_needs(args.season))


if __name__ == "__main__":
    main()
