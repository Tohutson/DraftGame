import random
from typing import Any, Dict, Iterable, List


POSITION_VALUE = {
    "QB": 20,
    "EDGE": 14,
    "OT": 13,
    "WR": 12,
    "CB": 11,
    "DT": 10,
    "LB": 8,
    "S": 7,
    "IOL": 7,
    "TE": 6,
    "RB": 5,
    "K": 1,
    "P": 1,
}


def _team_pick_counts(picks: Iterable[Dict[str, Any]], team_id: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for pick in picks:
        if pick.get("team_id") != team_id or not pick.get("position"):
            continue
        counts[pick["position"]] = counts.get(pick["position"], 0) + 1
    return counts


def choose_simulated_pick(
    prospects: List[Dict[str, Any]],
    team: Dict[str, Any],
    picks: List[Dict[str, Any]],
    seed: int,
    overall: int,
) -> Dict[str, Any]:
    rng = random.Random(f"{seed}:{team['id']}:{overall}")
    needs = set(team.get("needs", []))
    counts = _team_pick_counts(picks, team["id"])

    best = None
    best_score = float("-inf")

    for prospect in prospects[:45]:
        rank_score = max(0, 260 - int(prospect.get("rank", 260)))
        need_bonus = 34 if prospect.get("position") in needs else 0
        value_bonus = POSITION_VALUE.get(prospect.get("position"), 4)
        repeat_penalty = counts.get(prospect.get("position"), 0) * 22
        noise = rng.uniform(-9, 9)
        score = rank_score + need_bonus + value_bonus - repeat_penalty + noise
        if score > best_score:
            best = prospect
            best_score = score

    return best or prospects[0]

