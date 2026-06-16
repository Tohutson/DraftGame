from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.data_loader import DataLoader, get_data_loader
from app.services.prospect_service import public_prospect
from app.services.reveal_service import build_reveal
from app.services.simulation_service import choose_simulated_pick


GAMES: Dict[str, Dict[str, Any]] = {}


class DraftGameService:
    def __init__(self, loader: Optional[DataLoader] = None):
        self.loader = loader or get_data_loader()

    def create_game(
        self, draft_year: int, user_team: Optional[str], rounds: int = 3, seed: int = 2026
    ) -> Dict[str, Any]:
        prospects = self.loader.prospects_for_year(draft_year)
        if not prospects:
            raise ValueError("Draft year not found")

        teams = self.loader.teams()
        if not teams:
            raise ValueError("No teams configured")

        team = self.loader.team_by_id(user_team or "") if user_team else teams[seed % len(teams)]
        if not team:
            raise ValueError("Team not found")

        max_rounds = min(rounds, max(1, len(prospects) // len(teams)))
        draft_order = self._build_draft_order(teams, max_rounds)
        game_id = str(uuid4())
        game = {
            "game_id": game_id,
            "draft_year": draft_year,
            "user_team": team,
            "rounds": max_rounds,
            "seed": seed,
            "current_index": 0,
            "status": "active",
            "available_ids": [p["hidden_id"] for p in prospects],
            "draft_order": draft_order,
            "picks": [],
        }
        GAMES[game_id] = game
        return game

    def get_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        return GAMES.get(game_id)

    def state(self, game: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "game_id": game["game_id"],
            "draft_year": game["draft_year"],
            "rounds": game["rounds"],
            "status": game["status"],
            "current_pick": self.current_pick(game),
            "user_team": game["user_team"],
            "team_needs": self.current_needs(game, game["user_team"]["id"]),
            "is_user_on_clock": self.is_user_on_clock(game),
            "picks": list(game["picks"]),
            "available_count": len(game["available_ids"]),
        }

    def board(self, game: Dict[str, Any]) -> List[Dict[str, Any]]:
        prospects = self._prospects_by_id(game)
        return [
            public_prospect(prospects[hidden_id])
            for hidden_id in game["available_ids"]
            if hidden_id in prospects
        ]

    def prospect_detail(self, game: Dict[str, Any], hidden_id: str) -> Dict[str, Any]:
        prospects = self._prospects_by_id(game)
        if hidden_id not in game["available_ids"] or hidden_id not in prospects:
            raise ValueError("Prospect not available")
        return public_prospect(prospects[hidden_id])

    def make_user_pick(self, game: Dict[str, Any], hidden_id: str) -> Dict[str, Any]:
        if game["status"] != "active":
            raise ValueError("Draft is complete")
        if not self.is_user_on_clock(game):
            raise PermissionError("User team is not on the clock")
        if hidden_id not in game["available_ids"]:
            raise ValueError("Prospect not available")
        self._record_pick(game, hidden_id)
        return self.state(game)

    def simulate_until_user_pick_or_complete(self, game: Dict[str, Any]) -> Dict[str, Any]:
        while game["status"] == "active" and not self.is_user_on_clock(game):
            current = self.current_pick(game)
            team = self.loader.team_by_id(current["team_id"])
            available = [p for p in self.loader.prospects_for_year(game["draft_year"]) if p["hidden_id"] in game["available_ids"]]
            prospect = choose_simulated_pick(
                available, team, game["picks"], game["seed"], current["overall"]
            )
            self._record_pick(game, prospect["hidden_id"])
        return self.state(game)

    def reveal(self, game: Dict[str, Any]) -> Dict[str, Any]:
        if game["status"] != "complete":
            raise ValueError("Draft is not complete")
        return build_reveal(game, self._prospects_by_id(game))

    def current_pick(self, game: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if game["current_index"] >= len(game["draft_order"]):
            return None
        pick = game["draft_order"][game["current_index"]]
        return {
            **pick,
            "team_name": self.loader.team_by_id(pick["team_id"])["name"],
        }

    def current_needs(self, game: Dict[str, Any], team_id: str) -> List[str]:
        team = self.loader.team_by_id(team_id)
        drafted = [
            pick["position"] for pick in game["picks"] if pick["team_id"] == team_id and pick.get("position")
        ]
        needs = list(team.get("needs", []))
        for position in drafted:
            if position in needs:
                needs.remove(position)
        return needs

    def is_user_on_clock(self, game: Dict[str, Any]) -> bool:
        pick = self.current_pick(game)
        return bool(pick and pick["team_id"] == game["user_team"]["id"])

    def _record_pick(self, game: Dict[str, Any], hidden_id: str) -> None:
        prospects = self._prospects_by_id(game)
        prospect = prospects[hidden_id]
        current = self.current_pick(game)
        pick = {
            "overall": current["overall"],
            "round": current["round"],
            "pick_in_round": current["pick_in_round"],
            "team_id": current["team_id"],
            "team_name": current["team_name"],
            "hidden_id": hidden_id,
            "fake_name": prospect["fake_name"],
            "position": prospect["position"],
            "college_team": prospect["college_team"],
            "is_user_pick": current["team_id"] == game["user_team"]["id"],
        }
        game["picks"].append(pick)
        game["available_ids"].remove(hidden_id)
        game["current_index"] += 1
        if game["current_index"] >= len(game["draft_order"]) or not game["available_ids"]:
            game["status"] = "complete"

    def _prospects_by_id(self, game: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {
            p["hidden_id"]: p
            for p in self.loader.prospects_for_year(game["draft_year"])
        }

    def _build_draft_order(self, teams: List[Dict[str, Any]], rounds: int) -> List[Dict[str, Any]]:
        order: List[Dict[str, Any]] = []
        overall = 1
        for round_number in range(1, rounds + 1):
            round_teams = teams if round_number % 2 == 1 else list(reversed(teams))
            for pick_in_round, team in enumerate(round_teams, start=1):
                order.append(
                    {
                        "overall": overall,
                        "round": round_number,
                        "pick_in_round": pick_in_round,
                        "team_id": team["id"],
                    }
                )
                overall += 1
        return order


def get_game_service() -> DraftGameService:
    return DraftGameService()

