from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.database import db_path
from app.data_loader import get_data_loader
from app.models.schemas import MakePickRequest, StartGameRequest
from app.services.draft_year_data_service import ValidationService, get_draft_year_data_service
from app.services.game_service import get_game_service
from app.services.prospect_service import assert_no_private_fields

router = APIRouter(prefix="/api", tags=["draft"])


def _service():
    return get_game_service()


def _game_or_404(game_id: str):
    game = _service().get_game(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game


@router.get("/draft-years")
def draft_years():
    return get_data_loader().draft_years()


@router.get("/data/draft-years")
def data_draft_years():
    return get_draft_year_data_service().list_draft_years()


@router.get("/data/available-draft-years")
def available_draft_years():
    return draft_years()


@router.get("/data/status")
def data_status():
    loader = get_data_loader()
    built_years = loader.draft_years()
    statuses = get_draft_year_data_service().list_draft_years()
    settings = get_settings()
    latest_reasonable_draft_year = max(settings.default_draft_year, datetime.utcnow().year - 1)
    year_options = list(range(2018, latest_reasonable_draft_year + 1))
    return {
        "available_draft_years": built_years,
        "draft_years": statuses,
        "draft_year_options": year_options,
        "default_draft_year": settings.default_draft_year if settings.default_draft_year in built_years else (built_years[-1] if built_years else settings.default_draft_year),
        "database_path": str(db_path()),
        "cfbd_configured": bool(settings.cfbd_api_key),
        "prospect_count": sum(len(loader.prospects_for_year(year)) for year in built_years),
    }


@router.post("/data/build")
def build_data(draft_year: int, through_season: int = 2025, force: bool = False):
    return build_draft_year(draft_year, through_season, force)


@router.post("/data/draft-years/{draft_year}/build")
def build_draft_year(draft_year: int, through_season: int = 2025, force: bool = False):
    try:
        return get_draft_year_data_service().build_draft_year(draft_year, through_season, force)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/data/draft-years/{draft_year}/status")
def data_draft_year_status(draft_year: int):
    return get_draft_year_data_service().build_status(draft_year)


@router.get("/data/draft-classes/{draft_year}/validation")
def data_draft_class_validation(draft_year: int):
    result = ValidationService().validate_draft_year(draft_year)
    if not result["valid"]:
        raise HTTPException(status_code=422, detail=result)
    return result


@router.get("/teams")
def teams(draft_year: Optional[int] = None):
    return get_data_loader().teams(draft_year)


@router.get("/data/teams")
def data_teams(draft_year: Optional[int] = None):
    return teams(draft_year)


@router.get("/data/draft-classes/{draft_year}/summary")
def data_draft_class_summary(draft_year: int):
    prospects = get_data_loader().prospects_for_year(draft_year)
    if not prospects:
        raise HTTPException(status_code=404, detail="Draft year not found")
    positions = sorted({prospect["position"] for prospect in prospects})
    teams_in_class = sorted({
        prospect.get("actual_draft", {}).get("team")
        for prospect in prospects
        if prospect.get("actual_draft", {}).get("team")
    })
    return {
        "draft_year": draft_year,
        "prospect_count": len(prospects),
        "rounds": max(prospect.get("actual_draft", {}).get("round") or 1 for prospect in prospects),
        "positions": positions,
        "teams": teams_in_class,
    }


@router.post("/games")
def create_game(req: StartGameRequest):
    try:
        game = _service().create_game(
            draft_year=req.draft_year,
            user_team=req.user_team,
            rounds=req.rounds,
            seed=req.seed,
        )
        state = _service().state(game)
        assert_no_private_fields(state)
        return state
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/games/{game_id}")
def get_game(game_id: str):
    state = _service().state(_game_or_404(game_id))
    assert_no_private_fields(state)
    return state


@router.post("/games/{game_id}/simulate")
def simulate(game_id: str):
    state = _service().simulate_until_user_pick_or_complete(_game_or_404(game_id))
    assert_no_private_fields(state)
    return state


@router.post("/games/{game_id}/simulate-until-user-pick")
def simulate_until_user_pick(game_id: str):
    return simulate(game_id)


@router.post("/games/{game_id}/simulate-rest")
def simulate_rest(game_id: str):
    state = _service().simulate_to_completion(_game_or_404(game_id))
    assert_no_private_fields(state)
    return state


@router.get("/games/{game_id}/board")
def board(game_id: str):
    payload = {"prospects": _service().board(_game_or_404(game_id))}
    assert_no_private_fields(payload)
    return payload


@router.get("/games/{game_id}/draft-board")
def draft_board(game_id: str):
    return board(game_id)


@router.get("/games/{game_id}/prospects/{hidden_id}")
def prospect_detail(game_id: str, hidden_id: str):
    try:
        payload = _service().prospect_detail(_game_or_404(game_id), hidden_id)
        assert_no_private_fields(payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/games/{game_id}/draft-board/{hidden_player_id}")
def draft_board_prospect_detail(game_id: str, hidden_player_id: str):
    return prospect_detail(game_id, hidden_player_id)


@router.post("/games/{game_id}/pick")
def make_pick(game_id: str, req: MakePickRequest):
    try:
        hidden_id = req.hidden_player_id or req.hidden_id
        if not hidden_id:
            raise ValueError("hidden_player_id is required")
        state = _service().make_user_pick(_game_or_404(game_id), hidden_id)
        assert_no_private_fields(state)
        return state
    except PermissionError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/games/{game_id}/reveal")
def reveal(game_id: str):
    try:
        return _service().reveal(_game_or_404(game_id))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/games/{game_id}/results")
def results(game_id: str):
    return reveal(game_id)
