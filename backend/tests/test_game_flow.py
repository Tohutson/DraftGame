import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient


class FakeNFLVerse:
    def __init__(self):
        self.draft_pick_calls = 0
        self.roster_calls = 0
        self.player_stat_calls = 0
        self.version = 1

    def draft_picks(self, years=None, force=False):
        self.draft_pick_calls += 1
        year = years[0]
        suffix = "" if self.version == 1 else " II"
        return [
            {
                "draft_year": year,
                "overall": 1,
                "round": 1,
                "pick": 1,
                "team": "STL",
                "player_name": f"Real Quarterback{suffix}",
                "position": "QB",
                "college": "State",
                "player_id": f"qb-{self.version}",
            },
            {
                "draft_year": year,
                "overall": 2,
                "round": 1,
                "pick": 2,
                "team": "KC",
                "player_name": "Real Receiver",
                "position": "WR",
                "college": "Tech",
                "player_id": "wr-1",
            },
        ]

    def rosters(self, seasons, force=False):
        self.roster_calls += 1
        season = seasons[0]
        return [
            {"season": season, "team": "STL", "player_name": "Roster QB", "player_id": "r1", "position": "QB", "age": 30},
            {"season": season, "team": "KC", "player_name": "Roster WR", "player_id": "r2", "position": "WR", "age": 28},
        ]

    def player_stats(self, seasons, force=False):
        self.player_stat_calls += 1
        return [
            {
                "season": seasons[0],
                "week": 1,
                "player_id": f"qb-{self.version}",
                "player_name": f"Real Quarterback{'' if self.version == 1 else ' II'}",
                "position": "QB",
                "passing_yards": 300,
                "passing_tds": 2,
                "interceptions": 1,
            },
            {
                "season": seasons[0],
                "week": 1,
                "player_id": "wr-1",
                "player_name": "Real Receiver",
                "position": "WR",
                "receptions": 5,
                "receiving_yards": 80,
                "receiving_tds": 1,
            },
        ]

    def seasonal_rosters(self, seasons, force=False):
        return []

    def weekly_rosters(self, seasons, force=False):
        return []

    def combine(self, years=None, force=False):
        return [{"player_name": "Real Quarterback", "height": 75, "weight": 220, "forty": 4.8}]


class FakeCFBD:
    available = False


@pytest.fixture()
def isolated_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("CFBD_API_KEY", raising=False)
    monkeypatch.delenv("COLLEGE_FOOTBALL_DATA_API_KEY", raising=False)

    import app.data_loader as data_loader
    import app.services.game_service as game_service
    from app.database import init_db

    data_loader.get_data_loader.cache_clear()
    game_service.GAMES.clear()
    init_db()

    fake_nfl = FakeNFLVerse()

    from app.services.draft_year_data_service import DraftYearDataService

    data_service = DraftYearDataService(nflverse=fake_nfl, cfbd=FakeCFBD())
    monkeypatch.setattr(game_service, "get_draft_year_data_service", lambda: data_service)
    import app.api.draft as draft_api

    monkeypatch.setattr(draft_api, "get_draft_year_data_service", lambda: data_service)

    import main

    return TestClient(main.app), data_service, fake_nfl


def assert_no_private_fields(payload):
    from app.services.prospect_service import PRIVATE_FIELDS

    if isinstance(payload, dict):
        assert not PRIVATE_FIELDS.intersection(payload.keys())
        for value in payload.values():
            assert_no_private_fields(value)
    elif isinstance(payload, list):
        for item in payload:
            assert_no_private_fields(item)


def test_db_initializes_correctly(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))
    from app.database import table_counts

    counts = table_counts()
    assert counts["data_builds"] == 0
    assert "prospects" in counts


def test_missing_draft_year_triggers_build_and_persists(isolated_app):
    client, _service, fake_nfl = isolated_app

    response = client.post("/api/games", json={"draft_year": 2021, "user_team": "LAR", "rounds": 1, "seed": 1})
    assert response.status_code == 200
    assert fake_nfl.draft_pick_calls == 1
    assert response.json()["current_pick"]["team_id"] == "LAR"

    status = client.get("/api/data/draft-years/2021/status").json()
    assert status["status"] == "partial"
    assert status["validation_summary"]["counts"]["prospects"] == 2


def test_existing_valid_draft_year_does_not_refetch(isolated_app):
    client, _service, fake_nfl = isolated_app

    client.post("/api/games", json={"draft_year": 2021, "user_team": "LAR", "rounds": 1, "seed": 1})
    client.post("/api/games", json={"draft_year": 2021, "user_team": "KC", "rounds": 1, "seed": 2})

    assert fake_nfl.draft_pick_calls == 1


def test_force_rebuild_replaces_data(isolated_app):
    client, _service, fake_nfl = isolated_app

    client.post("/api/data/draft-years/2021/build?through_season=2021")
    fake_nfl.version = 2
    rebuilt = client.post("/api/data/draft-years/2021/build?through_season=2021&force=true")
    assert rebuilt.status_code == 200

    from app.data_loader import DataLoader

    prospects = DataLoader().prospects_for_year(2021)
    assert prospects[0]["real_name"] == "Real Quarterback II"


def test_team_abbreviation_normalization_is_consistent(isolated_app):
    client, _service, _fake_nfl = isolated_app

    client.post("/api/data/draft-years/2021/build?through_season=2021")
    teams = client.get("/api/data/teams?draft_year=2021").json()
    assert any(team["id"] == "LAR" for team in teams)
    assert all(team["id"] != "STL" for team in teams)


def test_old_csv_data_is_not_used_in_normal_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_CACHE_DIR", str(tmp_path))

    from app.services.draft_year_data_service import DraftYearDataService
    from app.data_sources.nflverse_client import MissingNFLReadPy

    class MissingNFL:
        def draft_picks(self, years=None, force=False):
            raise MissingNFLReadPy("nflreadpy is not installed")

    service = DraftYearDataService(nflverse=MissingNFL(), cfbd=FakeCFBD())
    with pytest.raises(MissingNFLReadPy):
        service.build_draft_year(2021, 2021)


def test_pre_reveal_endpoints_do_not_leak_private_fields(isolated_app):
    client, _service, _fake_nfl = isolated_app

    game = client.post("/api/games", json={"draft_year": 2021, "user_team": "LAR", "rounds": 1, "seed": 1}).json()
    board = client.get(f"/api/games/{game['game_id']}/draft-board").json()
    state = client.get(f"/api/games/{game['game_id']}").json()

    assert_no_private_fields(board)
    assert_no_private_fields(state)


def test_results_reveal_only_after_completion(isolated_app):
    client, _service, _fake_nfl = isolated_app

    game = client.post("/api/games", json={"draft_year": 2021, "user_team": "LAR", "rounds": 1, "seed": 1}).json()
    early = client.get(f"/api/games/{game['game_id']}/results")
    assert early.status_code == 400

    board = client.get(f"/api/games/{game['game_id']}/draft-board").json()["prospects"]
    client.post(f"/api/games/{game['game_id']}/pick", json={"hidden_id": board[0]["hidden_id"]})
    done = client.post(f"/api/games/{game['game_id']}/simulate-rest").json()
    assert done["status"] == "complete"

    reveal = client.get(f"/api/games/{game['game_id']}/results").json()
    assert reveal["user_picks"][0]["real_name"]
    assert reveal["user_picks"][0]["career_value"] >= 0


def test_source_consistency_validation_catches_mixed_sample(isolated_app):
    client, _service, _fake_nfl = isolated_app

    client.post("/api/data/draft-years/2021/build?through_season=2021")
    from app.database import session

    with session() as conn:
        conn.execute("UPDATE prospects SET source = 'sample' WHERE draft_year = 2021 AND rank = 1")

    from app.services.draft_year_data_service import ValidationService

    result = ValidationService().validate_draft_year(2021)
    assert result["valid"] is False
    assert "mixed real and sample/fallback sources" in result["errors"]


def test_persisted_db_survives_service_restart(isolated_app):
    client, _service, _fake_nfl = isolated_app

    client.post("/api/data/draft-years/2021/build?through_season=2021")

    from app.data_loader import DataLoader
    from app.services.game_service import DraftGameService

    restarted = DraftGameService(loader=DataLoader())
    assert restarted.loader.prospects_for_year(2021)
