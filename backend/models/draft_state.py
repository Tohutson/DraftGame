from uuid import uuid4
from services.draft_logic import player_ids_by_year, draft_order_by_year

DRAFTS = {}


def create_draft(year, team):
    draft_id = str(uuid4())

    DRAFTS[draft_id] = {
        "year": year,
        "user_team": team,
        "index": 0,
        "round": 1,
        "pick": 1,
        "available_players": player_ids_by_year(year),
        "draft_order": draft_order_by_year(year),
        "status": "simulating",  # simulating → waiting_for_user → complete
    }
    return draft_id


def get_draft(draft_id: str):
    return DRAFTS.get(draft_id)
