from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StartGameRequest(BaseModel):
    draft_year: int
    user_team: Optional[str] = None
    rounds: Optional[int] = Field(default=None, ge=1, le=7)
    seed: int = 2026


class MakePickRequest(BaseModel):
    hidden_id: Optional[str] = None
    hidden_player_id: Optional[str] = None


class TeamPublic(BaseModel):
    id: str
    name: str
    abbreviation: str
    needs: List[str]


class ProspectPublic(BaseModel):
    hidden_id: str
    hidden_player_id: str
    fake_name: str
    draft_year: int
    rank: int
    position: str
    college_team: str
    conference: Optional[str] = None
    height: Optional[int] = None
    weight: Optional[int] = None
    combine_summary: Optional[str] = None
    college_stats: Dict[str, Any] = Field(default_factory=dict)
    projected_round: Optional[int] = None
    projected_pick: Optional[int] = None
    scouting_blurb: Optional[str] = None
    scouting_report: List[str] = Field(default_factory=list)


class DraftPickPublic(BaseModel):
    overall: int
    round: int
    pick_in_round: int
    team_id: str
    team_name: str
    hidden_id: Optional[str] = None
    fake_name: Optional[str] = None
    position: Optional[str] = None
    college_team: Optional[str] = None
    is_user_pick: bool = False
