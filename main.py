import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from uuid import uuid4

app = FastAPI()

# -----------------------
# Data loading
# -----------------------


def load_players():
    players = pd.read_csv("data/nfl_draft_prospects.csv")
    college_stats = pd.read_csv("data/college_statistics.csv")
    profiles = pd.read_csv("data/nfl_draft_profiles.csv")

    full_players = players.merge(profiles, on="player_id", how="left")
    return full_players, college_stats


PLAYERS, PLAYER_STATS = load_players()

# Pre-split by year
PLAYERS_BY_YEAR = {year: df for year, df in PLAYERS.groupby("draft_year")}

DRAFTS = {}

# -----------------------
# Helpers
# -----------------------


def player_ids_by_year(year):
    return set(PLAYERS_BY_YEAR[year]["player_id"])


def draft_order_by_year(year):
    df = PLAYERS_BY_YEAR[year].dropna(subset=["overall"]).sort_values("overall")
    for _, row in df.iterrows():
        print(row["overall"])

    return [
        {
            "overall": int(row["overall"]),
            "round": int(row["round"]),
            "pick": int(row["pick"]),
            "team": row["team"],
            "player_id": None,
        }
        for _, row in df.iterrows()
    ]


def new_draft_state(year, team):
    return {
        "year": year,
        "user_team": team,
        "index": 0,
        "round": 1,
        "pick": 1,
        "available_players": player_ids_by_year(year),
        "draft_order": draft_order_by_year(year),
        "status": "simulating",  # simulating → waiting_for_user → complete
    }


def user_turn(draft):
    current = draft["draft_order"][draft["index"]]
    return current["team"] == draft["user_team"]


# -----------------------
# Core engine
# -----------------------


def update_status(draft):
    if draft["index"] >= len(draft["draft_order"]):
        draft["status"] = "complete"
        return

    if user_turn(draft):
        draft["status"] = "waiting_for_user"
    else:
        draft["status"] = "simulating"


def advance_metadata(draft):
    if draft["index"] >= len(draft["draft_order"]):
        return

    next_pick = draft["draft_order"][draft["index"]]
    draft["round"] = next_pick["round"]
    draft["pick"] = next_pick["pick"]


def draft_player(draft, player_id):
    draft["available_players"].remove(player_id)

    pick = draft["draft_order"][draft["index"]]
    pick["player_id"] = player_id

    draft["index"] += 1
    advance_metadata(draft)
    update_status(draft)


def simulate_pick(draft):
    year_df = PLAYERS_BY_YEAR[draft["year"]]
    overall = draft["index"] + 1

    row = year_df[year_df["overall"] == overall]

    # Filter available players
    available = year_df[year_df["player_id"].isin(draft["available_players"])]

    # If real pick exists and available → take it
    if len(row) > 0:
        pid = row.iloc[0]["player_id"]
        if pid in draft["available_players"]:
            draft_player(draft, pid)
            return

    # Otherwise choose best available
    if len(available) == 0:
        update_status(draft)
        return

    position = row.iloc[0]["position"] if len(row) > 0 else None

    if position:
        same_position = available[available["position"] == position]
    else:
        same_position = pd.DataFrame()

    if len(same_position) > 0:
        best = same_position.sort_values("pos_rk").iloc[0]
    else:
        best = available.sort_values("ovr_rk").iloc[0]

    draft_player(draft, best["player_id"])


# -----------------------
# API models
# -----------------------


class StartDraftRequest(BaseModel):
    year: int
    user_team: str


# -----------------------
# API endpoints
# -----------------------


@app.get("/draft/years")
def get_years():
    return sorted(PLAYERS_BY_YEAR.keys())


@app.get("/draft/teams")
def get_teams(year: int):
    if year not in PLAYERS_BY_YEAR:
        raise HTTPException(404, "Year not found")

    df = PLAYERS_BY_YEAR[year]
    return sorted(df["team"].dropna().unique().tolist())


@app.post("/draft/start")
def start_draft(req: StartDraftRequest):
    if req.year not in PLAYERS_BY_YEAR:
        raise HTTPException(404, "Year not found")

    draft_id = str(uuid4())
    DRAFTS[draft_id] = new_draft_state(req.year, req.user_team)
    return {"draft_id": draft_id}


@app.get("/draft/{draft_id}")
def draft_status(draft_id: str):
    draft = DRAFTS.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")

    return {
        "round": draft["round"],
        "pick": draft["pick"],
        "status": draft["status"],
        "index": draft["index"],
    }


@app.post("/draft/{draft_id}/advance")
def advance(draft_id: str):
    draft = DRAFTS.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")

    while draft["status"] == "simulating":
        simulate_pick(draft)

    return {
        "round": draft["round"],
        "pick": draft["pick"],
        "status": draft["status"],
    }


@app.post("/draft/{draft_id}/pick/{player_id}")
def pick(draft_id: str, player_id: int):
    draft = DRAFTS.get(draft_id)
    if not draft:
        raise HTTPException(404, "Draft not found")

    if draft["status"] != "waiting_for_user":
        raise HTTPException(400, "Not your turn")

    if player_id not in draft["available_players"]:
        raise HTTPException(400, "Player not available")

    draft_player(draft, player_id)

    # resume sim automatically
    while draft["status"] == "simulating":
        simulate_pick(draft)

    return {
        "round": draft["round"],
        "pick": draft["pick"],
        "status": draft["status"],
    }
