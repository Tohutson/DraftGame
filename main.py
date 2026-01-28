import pandas as pd
from fastapi import FastAPI
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


def new_draft_state(players_ids, year):
    return {
        "year": year,
        "round": 1,
        "pick": 1,
        "available_players": players_ids,
        "teams": {
            "TEAM_1": [],
            "TEAM_2": [],
        },
    }


@app.post("/draft/start")
def start_draft(year: int):
    draft_id = str(uuid4())  # UUIDs need to be JSON serializable
    player_ids = player_ids_by_year(year)
    DRAFTS[draft_id] = new_draft_state(player_ids)
    return {"draft_id": draft_id}
