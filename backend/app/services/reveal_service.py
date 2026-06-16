from typing import Any, Dict, List


def expected_value(overall: int) -> float:
    if overall <= 10:
        return 70
    if overall <= 32:
        return 55
    if overall <= 64:
        return 38
    if overall <= 96:
        return 25
    return 14


def letter_grade(delta: float) -> str:
    if delta >= 25:
        return "A"
    if delta >= 12:
        return "B"
    if delta >= -4:
        return "C"
    if delta >= -16:
        return "D"
    return "F"


def build_reveal(game: Dict[str, Any], prospects_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    user_picks: List[Dict[str, Any]] = []
    total_delta = 0.0

    drafted_ids = {pick["hidden_id"] for pick in game["picks"] if pick.get("hidden_id")}

    for pick in game["picks"]:
        if not pick.get("is_user_pick"):
            continue
        prospect = prospects_by_id[pick["hidden_id"]]
        value = float(prospect.get("career_value") or 0)
        expected = expected_value(int(pick["overall"]))
        delta = value - expected
        total_delta += delta
        user_picks.append(
            {
                **pick,
                "fake_name": prospect["fake_name"],
                "real_name": prospect["real_name"],
                "real_player_id": prospect.get("real_player_id"),
                "actual_draft": prospect.get("actual_draft"),
                "career_summary": prospect.get("career_summary", {}),
                "career_value": value,
                "expected_value": expected,
                "outcome_label": prospect.get("outcome_label"),
                "reveal_blurb": prospect.get("reveal_blurb"),
                "value_delta": round(delta, 1),
            }
        )

    available_misses = [
        p for p in prospects_by_id.values() if p["hidden_id"] not in drafted_ids
    ]
    best_missed = sorted(
        available_misses, key=lambda p: float(p.get("career_value") or 0), reverse=True
    )[:5]

    grade = letter_grade(total_delta / max(len(user_picks), 1))
    return {
        "game_id": game["game_id"],
        "user_team": game["user_team"],
        "draft_year": game["draft_year"],
        "rounds": game["rounds"],
        "grade": grade,
        "summary": f"Your class finished {round(total_delta, 1)} value points versus expectation.",
        "user_picks": user_picks,
        "best_players_missed": [
            {
                "hidden_id": p["hidden_id"],
                "fake_name": p["fake_name"],
                "real_name": p["real_name"],
                "position": p["position"],
                "college_team": p["college_team"],
                "career_value": p.get("career_value", 0),
                "outcome_label": p.get("outcome_label"),
            }
            for p in best_missed
        ],
    }

