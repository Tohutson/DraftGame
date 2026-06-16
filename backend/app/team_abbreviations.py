from typing import Any


TEAM_ALIASES = {
    "LA": "LAR",
    "STL": "LAR",
    "WAS": "WSH",
}


def normalize_team_abbr(value: Any) -> str:
    team = str(value or "").upper()
    return TEAM_ALIASES.get(team, team)
