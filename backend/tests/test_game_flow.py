import pytest
from fastapi.testclient import TestClient

from app.data_loader import get_data_loader
from app.services.game_service import DraftGameService
from app.services.prospect_service import PRIVATE_FIELDS
from main import app


client = TestClient(app)


def assert_no_private_fields(payload):
    if isinstance(payload, dict):
        assert not PRIVATE_FIELDS.intersection(payload.keys())
        for value in payload.values():
            assert_no_private_fields(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_private_fields(item)


def test_game_start_creates_valid_state_without_private_fields():
    loader = get_data_loader()
    year = loader.draft_years()[-1]
    first_team = loader.teams()[0]["id"]
    response = client.post(
        "/api/games",
        json={"draft_year": year, "user_team": first_team, "rounds": 1, "seed": 1},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["game_id"]
    assert data["status"] == "active"
    assert data["current_pick"]["team_id"] == first_team
    assert data["is_user_on_clock"] is True
    assert_no_private_fields(data)


def test_user_can_pick_only_when_on_clock():
    year = get_data_loader().draft_years()[-1]
    game = client.post(
        "/api/games",
        json={"draft_year": year, "user_team": "KC", "rounds": 1, "seed": 2},
    ).json()
    board = client.get(f"/api/games/{game['game_id']}/board").json()["prospects"]
    blocked = client.post(
        f"/api/games/{game['game_id']}/pick",
        json={"hidden_id": board[0]["hidden_id"]},
    )
    assert blocked.status_code == 400

    simulated = client.post(f"/api/games/{game['game_id']}/simulate").json()
    assert simulated["is_user_on_clock"] is True
    pick = client.post(
        f"/api/games/{game['game_id']}/pick",
        json={"hidden_id": board[-1]["hidden_id"]},
    )
    assert pick.status_code == 200


def test_other_teams_simulate_without_duplicates_and_draft_ends():
    service = DraftGameService()
    year = service.loader.draft_years()[-1]
    game = service.create_game(year, "KC", rounds=1, seed=3)
    state = service.simulate_until_user_pick_or_complete(game)
    assert state["is_user_on_clock"] is True
    drafted_ids = [pick["hidden_id"] for pick in state["picks"]]
    assert len(drafted_ids) == len(set(drafted_ids))

    hidden_id = game["available_ids"][0]
    service.make_user_pick(game, hidden_id)
    final_state = service.simulate_until_user_pick_or_complete(game)
    assert final_state["status"] == "complete"
    all_ids = [pick["hidden_id"] for pick in game["picks"]]
    assert len(all_ids) == len(set(all_ids))


def test_reveal_only_after_completion_and_includes_real_names():
    year = get_data_loader().draft_years()[-1]
    game = client.post(
        "/api/games",
        json={"draft_year": year, "user_team": "KC", "rounds": 1, "seed": 4},
    ).json()
    early = client.get(f"/api/games/{game['game_id']}/reveal")
    assert early.status_code == 400

    state = client.post(f"/api/games/{game['game_id']}/simulate").json()
    board = client.get(f"/api/games/{game['game_id']}/board").json()["prospects"]
    client.post(
        f"/api/games/{game['game_id']}/pick",
        json={"hidden_id": board[0]["hidden_id"]},
    )
    state = client.post(f"/api/games/{game['game_id']}/simulate").json()
    assert state["status"] == "complete"
    reveal = client.get(f"/api/games/{game['game_id']}/reveal").json()
    assert reveal["user_picks"][0]["real_name"]
    assert reveal["user_picks"][0]["career_summary"]


def test_simulation_prefers_team_needs_roughly():
    service = DraftGameService()
    year = service.loader.draft_years()[-1]
    game = service.create_game(year, "KC", rounds=1, seed=5)
    state = service.simulate_until_user_pick_or_complete(game)
    need_hits = 0
    checked = 0
    for pick in state["picks"][:20]:
        team = service.loader.team_by_id(pick["team_id"])
        if pick["position"] in team["needs"]:
            need_hits += 1
        checked += 1
    assert checked
    assert need_hits / checked >= 0.25


def test_data_loader_handles_missing_fields(tmp_path):
    data_file = tmp_path / "sample_game_data.json"
    data_file.write_text(
        """{
          "teams": [{"id": "AAA", "name": "A Team", "abbreviation": "AAA", "needs": ["QB"]}],
          "prospects": [{"hidden_id": "x1", "real_name": "Real Player", "fake_name": "Fake Player", "draft_year": 2000, "rank": 1, "position": "QB", "college_team": "State"}]
        }""",
        encoding="utf-8",
    )
    from app.data_loader import DataLoader

    loader = DataLoader(data_file)
    assert loader.draft_years() == [2000]
    assert loader.prospects_for_year(2000)[0]["fake_name"] == "Fake Player"
