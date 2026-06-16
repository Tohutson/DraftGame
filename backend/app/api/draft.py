from fastapi import APIRouter, HTTPException

from app.data_loader import get_data_loader
from app.models.schemas import MakePickRequest, StartGameRequest
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


@router.get("/teams")
def teams():
    return get_data_loader().teams()


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


@router.get("/games/{game_id}/board")
def board(game_id: str):
    payload = {"prospects": _service().board(_game_or_404(game_id))}
    assert_no_private_fields(payload)
    return payload


@router.get("/games/{game_id}/prospects/{hidden_id}")
def prospect_detail(game_id: str, hidden_id: str):
    try:
        payload = _service().prospect_detail(_game_or_404(game_id), hidden_id)
        assert_no_private_fields(payload)
        return payload
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/games/{game_id}/pick")
def make_pick(game_id: str, req: MakePickRequest):
    try:
        state = _service().make_user_pick(_game_or_404(game_id), req.hidden_id)
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

