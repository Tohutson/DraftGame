import pandas as pd
from fastapi import FastAPI
from fastapi import BaseModel
from uuid import uuid4

app = FastAPI()


def load_players():
    players = pd.read_csv("data/nfl_draft_prospects.csv")
    college_stats = pd.read_csv("data/college_statistics.csv")
    profiles = pd.read_csv("data/nfl_draft_profiles.csv")

    full_players = players.merge(profiles, on="player_id", how="left")
    return full_players, college_stats


PLAYERS, PLAYER_STATS = load_players()

DRAFTS = {}


def player_ids_by_year(year):
    return set(PLAYERS[PLAYERS["year"] == year]["player_id"])


def draft_order_by_year(year):
    players_year = PLAYERS[PLAYERS["year"] == year]
    draft_order_df = players_year.sort_values("overall")
    draft_order = [
        {
            "overall": int(row.overall),
            "round": int(row.round),
            "pick": int(row.pick),
            "team": row.team,
            "player_id": None,  # filled during draft
        }
        for _, row in draft_order_df.iterrows()
    ]
    return draft_order


def new_draft_state(year, team):
    return {
        "year": year,
        "user_team": team,
        "round": 1,
        "pick": 1,
        "index": 0,
        "available_players": player_ids_by_year(year),
        "draft_order": draft_order_by_year(year),
        "status": "waiting_for_user" | "simulating" | "complete",
    }


@app.get("/draft/years")
def get_years():
    years = PLAYERS["year"].dropna().unique().tolist()
    return years


@app.get("/draft/teams")
def get_teams(year: int):
    teams = PLAYERS[PLAYERS["year"] == year]["team"].dropna().unique().tolist()
    return teams


class StartDraftRequest(BaseModel):
    year: int
    user_team: str


@app.post("/draft/start")
def start_draft(req: StartDraftRequest):
    draft_id = str(uuid4())  # UUIDs need to be JSON serializable
    DRAFTS[draft_id] = new_draft_state(req.year, req.user_team)
    return {"draft_id": draft_id}


@app.get("/draft/{draft_id}")
def draft_status(draft_id: str):
    draft = DRAFTS[draft_id]
    return {"round": draft["round"], "pick": draft["pick"], "status": draft["status"]}


def user_turn(draft_id):
    draft = DRAFTS[draft_id]
    user_team = draft["user_team"]
    drafting_team = draft["draft_order"][draft["index"]]["team"]
    return user_team == drafting_team


def draft_player(draft_id, player_id):
    draft = DRAFTS[draft_id]

    draft["available_players"].remove(player_id)

    current_pick = draft["draft_order"][draft["index"]]
    current_pick["player_id"] = player_id

    draft["index"] += 1

    if draft["index"] < len(draft["draft_order"]):
        next_pick = draft["draft_order"][draft["index"]]
        draft["round"] = next_pick["round"]
        draft["pick"] = next_pick["pick"]
    else:
        draft["complete"] = True


def simulate_pick(draft_id):
    draft = DRAFTS[draft_id]
    overall = draft["index"] + 1

    row = PLAYERS[(PLAYERS["year"] == draft["year"]) & (PLAYERS["overall"] == overall)]

    # no real pick exists
    if len(row) == 0:

    player_id = row.iloc[0]["player_id"]

    if player_id in draft["available_players"]:
        draft_player(draft_id, player_id)


@app.post("/draft/{draft_id}/advance")
def advance(draft_id: str):
    while not user_turn(draft_id) and not DRAFTS[draft_id]["status"] == "complete":
        simulate_pick()
    return picks


@app.post("/draft/{draft_id}/pick/{player_id}")
def pick(draft_id: str, player_id: int):
    draft_player(draft_id, player_id)
