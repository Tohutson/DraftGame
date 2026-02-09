from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np

from data.players import PLAYERS_BY_YEAR, PLAYERS, PLAYER_STATS, PROFILES
from models.draft_state import DRAFTS, create_draft, get_draft
from services.draft_logic import simulate_pick, draft_player

router = APIRouter(prefix="/draft", tags=["draft"])

# -----------------------
# API models
# -----------------------


class StartDraftRequest(BaseModel):
    year: int
    user_team: str


# -----------------------
# Helpers
# -----------------------


def json_safe(val):
    """Convert Pandas/NumPy types and problematic floats to JSON-safe Python types."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (np.integer, np.int64)):
        return int(val)
    if isinstance(val, (np.floating, np.float64)):
        if np.isfinite(val):
            return float(val)
        else:
            return None  # handles inf/-inf
    return val


# -----------------------
# API endpoints
# -----------------------


@router.get("/years")
def get_years():
    return sorted(PLAYERS_BY_YEAR.keys())


@router.get("/teams")
def get_teams(year: int):
    df = PLAYERS_BY_YEAR.get(year)
    if df is None:
        raise HTTPException(status_code=404, detail="Year not found")

    return sorted(df["team"].dropna().unique().tolist())


@router.post("/start")
def start_draft(req: StartDraftRequest):
    if req.year not in PLAYERS_BY_YEAR:
        raise HTTPException(status_code=404, detail="Year not found")

    draft = create_draft(year=req.year, team=req.user_team)

    return {"draft_id": draft}


@router.get("/{draft_id}")
def draft_status(draft_id: str):
    draft = get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "round": draft["round"],
        "pick": draft["pick"],
        "status": draft["status"],
        "index": draft["index"],
    }


@router.post("/{draft_id}/advance")
def advance(draft_id: str):
    draft = get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    while draft["status"] == "simulating":
        simulate_pick(draft)

    return {
        "round": draft["round"],
        "pick": draft["pick"],
        "status": draft["status"],
    }


@router.post("/{draft_id}/pick/{player_id}")
def pick_player(draft_id: str, player_id: int):
    draft = get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    if draft["status"] != "waiting_for_user":
        raise HTTPException(status_code=400, detail="Not your turn")

    if player_id not in draft["available_players"]:
        raise HTTPException(status_code=400, detail="Player not available")

    draft_player(draft, player_id)

    while draft["status"] == "simulating":
        simulate_pick(draft)

    return {
        "round": draft["round"],
        "pick": draft["pick"],
        "status": draft["status"],
    }


@router.get("/{draft_id}/board")
def draft_board(draft_id: str):
    draft = get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    return {
        "year": draft["year"],
        "current_index": draft["index"],
        "board": draft["draft_order"],
        "status": draft["status"],
    }


@router.get("/{draft_id}/available")
def get_available_players(draft_id: str):
    draft = get_draft(draft_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    df = PLAYERS_BY_YEAR.get(draft["year"])
    if df is None:
        raise HTTPException(status_code=404, detail="No players for this draft year")

    available_df = df.loc[
        df.index.intersection(draft["available_players"])
    ].sort_values("overall")

    return [
        {
            "player_id": int(pid),
            "name": row["player_name"],
            "position": json_safe(row["position"]),
            "height": json_safe(row["height"]),
            "weight": json_safe(row["weight"]),
            "overall_rank": None if pd.isna(row["ovr_rk"]) else int(row["ovr_rk"]),
        }
        for pid, row in available_df.iterrows()
    ]


@router.get("/player/{player_id}")
def get_player(player_id: int):
    if player_id not in PLAYERS.index:
        raise HTTPException(status_code=404, detail="Player not found")

    player = PLAYERS.loc[player_id]
    stats = (
        {k: json_safe(v) for k, v in PLAYER_STATS.loc[player_id].to_dict().items()}
        if player_id in PLAYER_STATS.index
        else {}
    )
    profile = (
        {k: json_safe(v) for k, v in PROFILES.loc[player_id].to_dict().items()}
        if player_id in PROFILES.index
        else {}
    )

    return {
        "player_id": json_safe(player_id),
        "name": json_safe(player.player_name),
        "position": json_safe(player.position),
        "team": json_safe(player.team),
        "height": json_safe(player.height),
        "weight": json_safe(player.weight),
        "college": json_safe(player.school),
        "overall_rank": json_safe(player.ovr_rk),
        "stats": stats,
        "profile": profile,
    }
