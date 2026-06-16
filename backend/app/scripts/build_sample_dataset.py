import csv
import hashlib
import json
import math
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

TEAMS = [
    ("ARI", "Arizona Cardinals", ["WR", "EDGE", "CB"]),
    ("ATL", "Atlanta Falcons", ["EDGE", "QB", "CB"]),
    ("BAL", "Baltimore Ravens", ["OT", "WR", "EDGE"]),
    ("BUF", "Buffalo Bills", ["WR", "S", "DT"]),
    ("CAR", "Carolina Panthers", ["WR", "EDGE", "IOL"]),
    ("CHI", "Chicago Bears", ["QB", "EDGE", "WR"]),
    ("CIN", "Cincinnati Bengals", ["OT", "DT", "CB"]),
    ("CLE", "Cleveland Browns", ["WR", "DT", "LB"]),
    ("DAL", "Dallas Cowboys", ["OT", "RB", "LB"]),
    ("DEN", "Denver Broncos", ["QB", "CB", "TE"]),
    ("DET", "Detroit Lions", ["CB", "EDGE", "WR"]),
    ("GB", "Green Bay Packers", ["CB", "OT", "RB"]),
    ("HOU", "Houston Texans", ["DT", "CB", "WR"]),
    ("IND", "Indianapolis Colts", ["CB", "WR", "TE"]),
    ("JAX", "Jacksonville Jaguars", ["CB", "WR", "DT"]),
    ("KC", "Kansas City Chiefs", ["WR", "OT", "CB"]),
    ("LV", "Las Vegas Raiders", ["QB", "CB", "OT"]),
    ("LAC", "Los Angeles Chargers", ["WR", "OT", "CB"]),
    ("LAR", "Los Angeles Rams", ["EDGE", "OT", "CB"]),
    ("MIA", "Miami Dolphins", ["IOL", "DT", "TE"]),
    ("MIN", "Minnesota Vikings", ["QB", "EDGE", "IOL"]),
    ("NE", "New England Patriots", ["QB", "WR", "OT"]),
    ("NO", "New Orleans Saints", ["OT", "DT", "WR"]),
    ("NYG", "New York Giants", ["WR", "QB", "CB"]),
    ("NYJ", "New York Jets", ["OT", "WR", "S"]),
    ("PHI", "Philadelphia Eagles", ["CB", "LB", "S"]),
    ("PIT", "Pittsburgh Steelers", ["OT", "CB", "WR"]),
    ("SEA", "Seattle Seahawks", ["IOL", "EDGE", "S"]),
    ("SF", "San Francisco 49ers", ["OT", "CB", "IOL"]),
    ("TB", "Tampa Bay Buccaneers", ["EDGE", "IOL", "CB"]),
    ("TEN", "Tennessee Titans", ["OT", "WR", "EDGE"]),
    ("WAS", "Washington Commanders", ["QB", "OT", "CB"]),
]

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
    "P": "P",
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


def read_prospects() -> Iterable[Dict[str, Any]]:
    with (RAW_DATA / "nfl_draft_prospects.csv").open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def main() -> None:
    stats = load_stats()
    prospects: List[Dict[str, Any]] = []
    sample_year = 2021
    selected = [
        row for row in read_prospects()
        if row["draft_year"] == str(sample_year) and as_int(row.get("overall")) is not None
    ][:128]
    for row in selected:
        real_name = row["player_name"]
        rank = as_int(row.get("overall")) or len(prospects) + 1
        position = POSITION_MAP.get(clean(row.get("pos_abbr")) or "", clean(row.get("pos_abbr")) or "ATH")
        college_stats = key_stats(position, stats.get(row["player_id"], {}))
        summary, value, label = career_summary(position, rank)
        actual_team = clean(row.get("team_abbr")) or clean(row.get("team"))
        prospects.append(
            {
                "hidden_id": f"p{rank:03d}",
                "real_player_id": row["player_id"],
                "real_name": real_name,
                "fake_name": fake_name(real_name),
                "draft_year": sample_year,
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
                "actual_draft": {
                    "year": sample_year,
                    "round": as_int(row.get("round")),
                    "pick": as_int(row.get("pick")),
                    "overall": rank,
                    "team": actual_team,
                },
                "career_summary": summary,
                "career_value": value,
                "outcome_label": label,
                "reveal_blurb": f"{real_name} was selected {rank} overall in the {sample_year} NFL Draft. Sample career totals are cached for offline MVP play.",
            }
        )

    data = {
        "meta": {
            "dataset": "sample",
            "description": "Offline sample game data generated from bundled draft CSVs with deterministic fake names.",
        },
        "teams": [
            {"id": team_id, "name": name, "abbreviation": team_id.rstrip("2"), "needs": needs}
            for team_id, name, needs in TEAMS
        ],
        "prospects": prospects,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
    print(f"Wrote {OUT_FILE} with {len(prospects)} prospects")


if __name__ == "__main__":
    main()
