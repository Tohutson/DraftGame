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


def teams_by_year(year):
    players_year = PLAYERS[PLAYERS["year"] == year]
    teams = {team: [] for team in players_year["team"].dropna().unique()}
    return teams


def new_draft_state(year):
    return {
        "year": year,
        "round": 1,
        "pick": 1,
        "available_players": player_ids_by_year(year),
        "teams": teams_by_year(year),
    }


@app.post("/draft/start")
def start_draft(year: int):
    draft_id = str(uuid4())  # UUIDs need to be JSON serializable
    DRAFTS[draft_id] = new_draft_state(year)
    return {"draft_id": draft_id}
