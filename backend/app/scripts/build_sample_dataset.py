import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
RAW_DATA = ROOT / "data"
OUT_DIR = ROOT / "app" / "data"
OUT_FILE = OUT_DIR / "sample_game_data.json"

FIRST_NAMES = [
    "Marcus", "Darius", "Caleb", "Jordan", "Trey", "Evan", "Nolan", "Bryce",
    "Malik", "Jalen", "Cole", "Isaiah", "Dante", "Miles", "Grant", "Quinn",
]
LAST_NAMES = [
    "Brooks", "Carter", "Hayes", "Reed", "Bennett", "Foster", "Marshall", "Pierce",
    "Sutton", "Warren", "Coleman", "Bishop", "Porter", "Griffin", "Lawson", "Hale",
]

DEFAULT_NEEDS = ["QB", "OT", "EDGE", "WR", "CB", "DT", "IOL", "S", "LB", "TE", "RB"]
MODERN_NEEDS = {
    "ARI": ["WR", "EDGE", "CB"],
    "ATL": ["EDGE", "QB", "CB"],
    "BAL": ["OT", "WR", "EDGE"],
    "BUF": ["WR", "S", "DT"],
    "CAR": ["WR", "EDGE", "IOL"],
    "CHI": ["QB", "EDGE", "WR"],
    "CIN": ["OT", "DT", "CB"],
    "CLE": ["WR", "DT", "LB"],
    "DAL": ["OT", "RB", "LB"],
    "DEN": ["QB", "CB", "TE"],
    "DET": ["CB", "EDGE", "WR"],
    "GB": ["CB", "OT", "RB"],
    "HOU": ["DT", "CB", "WR"],
    "IND": ["CB", "WR", "TE"],
    "JAX": ["CB", "WR", "DT"],
    "KC": ["WR", "OT", "CB"],
    "LV": ["QB", "CB", "OT"],
    "LAC": ["WR", "OT", "CB"],
    "LAR": ["EDGE", "OT", "CB"],
    "MIA": ["IOL", "DT", "TE"],
    "MIN": ["QB", "EDGE", "IOL"],
    "NE": ["QB", "WR", "OT"],
    "NO": ["OT", "DT", "WR"],
    "NYG": ["WR", "QB", "CB"],
    "NYJ": ["OT", "WR", "S"],
    "PHI": ["CB", "LB", "S"],
    "PIT": ["OT", "CB", "WR"],
    "SEA": ["IOL", "EDGE", "S"],
    "SF": ["OT", "CB", "IOL"],
    "TB": ["EDGE", "IOL", "CB"],
    "TEN": ["OT", "WR", "EDGE"],
    "WAS": ["QB", "OT", "CB"],
}

POSITION_MAP = {
    "QB": "QB",
    "RB": "RB",
    "FB": "RB",
    "WR": "WR",
    "TE": "TE",
    "OT": "OT",
    "T": "OT",
    "OG": "IOL",
    "G": "IOL",
    "C": "IOL",
    "DE": "EDGE",
    "OLB": "EDGE",
    "DT": "DT",
    "ILB": "LB",
    "LB": "LB",
    "CB": "CB",
    "S": "S",
    "FS": "S",
    "SS": "S",
    "K": "K",
    "PK": "K",
    "P": "P",
    "LS": "IOL",
}


def clean(value: Any) -> Any:
    if value in ("", "NA", "nan", None):
        return None
    return value


def as_int(value: Any) -> int | None:
    value = clean(value)
    if value is None:
        return None
    try:
        numeric = float(value)
    except ValueError:
        return None
    if math.isnan(numeric):
        return None
    return int(numeric)


def fake_name(real_name: str, seed: int = 2026) -> str:
    digest = hashlib.sha256(f"{seed}:{real_name}".encode("utf-8")).hexdigest()
    first = FIRST_NAMES[int(digest[:4], 16) % len(FIRST_NAMES)]
    last = LAST_NAMES[int(digest[4:8], 16) % len(LAST_NAMES)]
    return f"{first} {last}"


def load_stats() -> Dict[str, Dict[str, float]]:
    stats: Dict[str, Dict[str, float]] = {}
    with (RAW_DATA / "college_statistics.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            player_id = row["player_id"]
            key = row["statistic"]
            try:
                value = float(row["value"])
            except ValueError:
                continue
            stats.setdefault(player_id, {})
            stats[player_id][key] = stats[player_id].get(key, 0) + value
    return stats


def load_profiles() -> Dict[str, Dict[str, Any]]:
    profiles: Dict[str, Dict[str, Any]] = {}
    with (RAW_DATA / "nfl_draft_profiles.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            profiles[row["player_id"]] = row
    return profiles


def key_stats(position: str, raw: Dict[str, float]) -> Dict[str, int]:
    wanted = {
        "QB": ["Passing Yards", "Passing Touchdowns", "Interceptions", "Rushing Yards"],
        "RB": ["Rushing Yards", "Rushing Touchdowns", "Receiving Yards", "Receptions"],
        "WR": ["Receptions", "Receiving Yards", "Receiving Touchdowns"],
        "TE": ["Receptions", "Receiving Yards", "Receiving Touchdowns"],
        "OT": ["Games Played"],
        "IOL": ["Games Played"],
        "EDGE": ["Total Tackles", "Sacks", "Tackles For Loss"],
        "DT": ["Total Tackles", "Sacks", "Tackles For Loss"],
        "LB": ["Total Tackles", "Sacks", "Interceptions"],
        "CB": ["Total Tackles", "Interceptions", "Passes Defended"],
        "S": ["Total Tackles", "Interceptions", "Passes Defended"],
    }.get(position, ["Total Tackles", "Games Played"])
    return {name: int(raw[name]) for name in wanted if name in raw}


def career_summary(position: str, rank: int) -> tuple[Dict[str, int], float, str]:
    value = max(5, round(98 - (rank * 0.8) + ((rank * 17) % 13), 1))
    games = max(1, int(value * 1.8))
    if position == "QB":
        summary = {"games": games, "starts": int(value * 0.9), "passing_yards": int(value * 420), "td": int(value * 2.2), "int": int(value * 1.1)}
    elif position == "RB":
        summary = {"games": games, "rushing_yards": int(value * 72), "receiving_yards": int(value * 28), "total_td": int(value * 0.8)}
    elif position in {"WR", "TE"}:
        summary = {"games": games, "receptions": int(value * 4.8), "receiving_yards": int(value * 62), "receiving_td": int(value * 0.5)}
    elif position in {"CB", "S", "LB"}:
        summary = {"games": games, "starts": int(value * 1.1), "tackles": int(value * 5.5), "sacks": int(value * 0.15), "interceptions": int(value * 0.12)}
    elif position in {"EDGE", "DT"}:
        summary = {"games": games, "starts": int(value), "tackles": int(value * 3.4), "sacks": int(value * 0.45)}
    else:
        summary = {"games": games, "starts": int(value * 1.2), "approximate_value": int(value)}
    if value >= 78:
        label = "Star"
    elif value >= 55:
        label = "Solid Starter"
    elif value >= 34:
        label = "Contributor"
    elif value >= 18:
        label = "Backup"
    else:
        label = "Bust/Minimal NFL impact"
    return summary, value, label


def sanitized_profile(real_name: str, fake: str, profile: Dict[str, Any] | None) -> List[str]:
    if not profile:
        return []
    names = [real_name]
    parts = [part for part in real_name.split() if len(part) > 2]
    names.extend(parts)
    report: List[str] = []
    for key in ("text1", "text2", "text3", "text4"):
        text = clean(profile.get(key)) if profile else None
        if not text:
            continue
        sanitized = str(text)
        for name in sorted(set(names), key=len, reverse=True):
            sanitized = re.sub(re.escape(name), fake, sanitized, flags=re.IGNORECASE)
        if sanitized.strip():
            report.append(sanitized.strip())
    return report


def read_prospects() -> Iterable[Dict[str, Any]]:
    with (RAW_DATA / "nfl_draft_prospects.csv").open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def main() -> None:
    stats = load_stats()
    profiles = load_profiles()
    prospects: List[Dict[str, Any]] = []
    selected = [
        row for row in read_prospects()
        if as_int(row.get("overall")) is not None and as_int(row.get("round")) is not None
    ]
    teams_by_id: Dict[str, Dict[str, Any]] = {}
    for row in selected:
        real_name = row["player_name"]
        year = as_int(row["draft_year"])
        rank = as_int(row.get("overall")) or len(prospects) + 1
        position = POSITION_MAP.get(clean(row.get("pos_abbr")) or "", clean(row.get("pos_abbr")) or "ATH")
        college_stats = key_stats(position, stats.get(row["player_id"], {}))
        summary, value, label = career_summary(position, rank)
        actual_team = clean(row.get("team_abbr")) or clean(row.get("team")) or "NFL"
        team_name = clean(row.get("team")) or actual_team
        if actual_team not in teams_by_id:
            offset = int(hashlib.sha256(actual_team.encode("utf-8")).hexdigest()[:4], 16)
            default_needs = [
                DEFAULT_NEEDS[(offset + index) % len(DEFAULT_NEEDS)]
                for index in range(3)
            ]
            teams_by_id[actual_team] = {
                "id": actual_team,
                "name": team_name,
                "abbreviation": actual_team,
                "needs": MODERN_NEEDS.get(actual_team, default_needs),
            }
        fake = fake_name(f"{year}:{real_name}:{rank}")
        report = sanitized_profile(real_name, fake, profiles.get(row["player_id"]))
        prospects.append(
            {
                "hidden_id": f"p{year}_{rank:03d}",
                "real_player_id": row["player_id"],
                "real_name": real_name,
                "fake_name": fake,
                "draft_year": year,
                "rank": rank,
                "position": position,
                "college_team": clean(row.get("school")) or "Not available",
                "conference": None,
                "height": as_int(row.get("height")),
                "weight": as_int(row.get("weight")),
                "combine_summary": "Not available",
                "college_stats": college_stats,
                "projected_round": as_int(row.get("round")),
                "projected_pick": as_int(row.get("overall")),
                "scouting_blurb": "College production and traits profile available. Real identity is hidden until reveal.",
                "scouting_report": report,
                "actual_draft": {
                    "year": year,
                    "round": as_int(row.get("round")),
                    "pick": as_int(row.get("pick")),
                    "overall": rank,
                    "team": actual_team,
                },
                "career_summary": summary,
                "career_value": value,
                "outcome_label": label,
                "reveal_blurb": f"{real_name} was selected {rank} overall in the {year} NFL Draft. Sample career totals are cached for offline MVP play.",
            }
        )

    data = {
        "meta": {
            "dataset": "full_local_cache",
            "description": "Offline cached game data generated from bundled draft CSVs with deterministic fake names.",
        },
        "teams": sorted(teams_by_id.values(), key=lambda team: team["name"]),
        "prospects": prospects,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print(f"Wrote {OUT_FILE} with {len(prospects)} prospects")


if __name__ == "__main__":
    main()
