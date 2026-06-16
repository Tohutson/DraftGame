from typing import Any, Dict


PUBLIC_PROSPECT_FIELDS = {
    "hidden_id",
    "fake_name",
    "draft_year",
    "rank",
    "position",
    "college_team",
    "conference",
    "height",
    "weight",
    "combine_summary",
    "college_stats",
    "projected_round",
    "projected_pick",
    "scouting_blurb",
}


PRIVATE_FIELDS = {
    "real_player_id",
    "real_name",
    "actual_draft",
    "career_summary",
    "career_value",
    "outcome_label",
    "reveal_blurb",
}


def public_prospect(prospect: Dict[str, Any]) -> Dict[str, Any]:
    return {field: prospect.get(field) for field in PUBLIC_PROSPECT_FIELDS}


def assert_no_private_fields(payload: Any) -> None:
    if isinstance(payload, dict):
        leaked = PRIVATE_FIELDS.intersection(payload.keys())
        if leaked:
            raise AssertionError(f"Private fields leaked: {sorted(leaked)}")
        for value in payload.values():
            assert_no_private_fields(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_private_fields(item)

