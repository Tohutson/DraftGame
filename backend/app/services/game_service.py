from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.data_loader import DataLoader, get_data_loader
from app.database import connect, dumps, init_db, loads, session
from app.services.draft_year_data_service import DraftYearDataService, get_draft_year_data_service
from app.services.prospect_service import public_prospect
from app.services.reveal_service import build_reveal
from app.services.simulation_service import choose_simulated_pick
from app.team_abbreviations import normalize_team_abbr


GAMES: Dict[str, Dict[str, Any]] = {}


class DraftGameService:
    def __init__(
        self,
        loader: Optional[DataLoader] = None,
        data_service: Optional[DraftYearDataService] = None,
    ):
        self.loader = loader or get_data_loader()
        self.data_service = data_service or get_draft_year_data_service()
        init_db()

    def create_game(
        self, draft_year: int, user_team: Optional[str], rounds: Optional[int] = None, seed: int = 2026
    ) -> Dict[str, Any]:
        self.data_service.ensure_draft_year_ready(draft_year)
        prospects = self.loader.prospects_for_year(draft_year)
        if not prospects:
            raise ValueError("Draft year not found")

        teams = self.loader.teams(draft_year)
        if not teams:
            raise ValueError("No teams configured")

        team = self.loader.team_by_id(normalize_team_abbr(user_team or "")) if user_team else teams[seed % len(teams)]
        if not team:
            raise ValueError("Team not found")

        draft_order = self._build_draft_order_from_prospects(prospects, rounds)
        game_id = str(uuid4())
        game = {
            "game_id": game_id,
            "draft_year": draft_year,
            "user_team": team,
            "rounds": max(pick["round"] for pick in draft_order),
            "seed": seed,
            "current_index": 0,
            "status": "active",
            "available_ids": [p["hidden_id"] for p in prospects],
            "draft_order": draft_order,
            "picks": [],
        }
        GAMES[game_id] = game
        self._persist_game(game)
        return game

    def get_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        if game_id in GAMES:
            return GAMES[game_id]
        game = self._load_game(game_id)
        if game:
            GAMES[game_id] = game
        return game

    def state(self, game: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "game_id": game["game_id"],
            "draft_year": game["draft_year"],
            "rounds": game["rounds"],
            "status": game["status"],
            "current_pick": self.current_pick(game),
            "user_team": game["user_team"],
            "team_needs": self.current_needs(game, game["user_team"]["id"]),
            "team_need_details": self.current_need_details(game, game["user_team"]["id"]),
            "team_needs_source": game["user_team"].get("needs_source", "sample_fallback"),
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
            self._simulate_current_pick(game)
        return self.state(game)

    def simulate_to_completion(self, game: Dict[str, Any]) -> Dict[str, Any]:
        while game["status"] == "active":
            self._simulate_current_pick(game)
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
            "team_name": self._team_for_game(game, pick["team_id"])["name"],
        }

    def current_needs(self, game: Dict[str, Any], team_id: str) -> List[str]:
        team = self._team_for_game(game, team_id)
        drafted = [
            pick["position"] for pick in game["picks"] if normalize_team_abbr(pick["team_id"]) == normalize_team_abbr(team_id) and pick.get("position")
        ]
        needs = list(team.get("needs", []))
        for position in drafted:
            if position in needs:
                needs.remove(position)
        return needs

    def current_need_details(self, game: Dict[str, Any], team_id: str) -> List[Dict[str, Any]]:
        team = self._team_for_game(game, team_id)
        drafted = {
            pick["position"] for pick in game["picks"] if normalize_team_abbr(pick["team_id"]) == normalize_team_abbr(team_id) and pick.get("position")
        }
        return [
            detail
            for detail in team.get("need_details", [])
            if detail.get("position") not in drafted
        ][:5]

    def is_user_on_clock(self, game: Dict[str, Any]) -> bool:
        pick = self.current_pick(game)
        return bool(pick and normalize_team_abbr(pick["team_id"]) == normalize_team_abbr(game["user_team"]["id"]))

    def _record_pick(self, game: Dict[str, Any], hidden_id: str) -> None:
        prospects = self._prospects_by_id(game)
        prospect = prospects[hidden_id]
        current = self.current_pick(game)
        pick = {
            "overall": current["overall"],
            "round": current["round"],
            "pick_in_round": current["pick_in_round"],
            "team_id": normalize_team_abbr(current["team_id"]),
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
        self._persist_game(game)
        self._persist_pick(game, pick, prospect.get("id"))

    def _prospects_by_id(self, game: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        return {
            p["hidden_id"]: p
            for p in self.loader.prospects_for_year(game["draft_year"])
        }

    def _simulate_current_pick(self, game: Dict[str, Any]) -> None:
        current = self.current_pick(game)
        team = self._team_for_game(game, current["team_id"])
        available = [
            p
            for p in self.loader.prospects_for_year(game["draft_year"])
            if p["hidden_id"] in game["available_ids"]
        ]
        prospect = choose_simulated_pick(
            available, team, game["picks"], game["seed"], current["overall"]
        )
        self._record_pick(game, prospect["hidden_id"])

    def _team_for_game(self, game: Dict[str, Any], team_id: str) -> Dict[str, Any]:
        team_id = normalize_team_abbr(team_id)
        for team in self.loader.teams(game["draft_year"]):
            if normalize_team_abbr(team["id"]) == team_id:
                return team
        team = self.loader.team_by_id(team_id)
        if not team:
            raise ValueError("Team not found")
        return team

    def _build_draft_order_from_prospects(
        self, prospects: List[Dict[str, Any]], rounds: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        order: List[Dict[str, Any]] = []
        for prospect in sorted(prospects, key=lambda p: int(p.get("rank", 9999))):
            draft = prospect.get("actual_draft") or {}
            if rounds is not None and int(draft.get("round") or 99) > rounds:
                continue
            team_id = normalize_team_abbr(draft.get("team"))
            if not team_id:
                continue
            order.append(
                {
                    "overall": int(draft.get("overall") or prospect["rank"]),
                    "round": int(draft.get("round") or 1),
                    "pick_in_round": int(draft.get("pick") or len(order) + 1),
                    "team_id": team_id,
                }
            )
        if not order:
            raise ValueError("Draft class has no draft order")
        return order

    def _persist_game(self, game: Dict[str, Any]) -> None:
        with session() as conn:
            conn.execute(
                """
                INSERT INTO games(
                    id, draft_year, user_team, current_pick, status, seed, rounds,
                    draft_order_json, available_ids_json, user_team_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    current_pick = excluded.current_pick,
                    status = excluded.status,
                    available_ids_json = excluded.available_ids_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    game["game_id"],
                    game["draft_year"],
                    game["user_team"]["id"],
                    game["current_index"] + 1,
                    game["status"],
                    game["seed"],
                    game["rounds"],
                    dumps(game["draft_order"]),
                    dumps(game["available_ids"]),
                    dumps(game["user_team"]),
                ),
            )

    def _persist_pick(self, game: Dict[str, Any], pick: Dict[str, Any], prospect_id: Any) -> None:
        with session() as conn:
            conn.execute(
                """
                INSERT INTO draft_picks(
                    game_id, pick_number, round, team_abbr, prospect_id, hidden_player_id,
                    fake_name, position, college_team, made_by_user
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id, pick_number) DO NOTHING
                """,
                (
                    game["game_id"],
                    pick["overall"],
                    pick["round"],
                    normalize_team_abbr(pick["team_id"]),
                    prospect_id,
                    pick.get("hidden_id"),
                    pick.get("fake_name"),
                    pick.get("position"),
                    pick.get("college_team"),
                    1 if pick.get("is_user_pick") else 0,
                ),
            )

    def _load_game(self, game_id: str) -> Optional[Dict[str, Any]]:
        with connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            if not row:
                return None
            picks = conn.execute(
                "SELECT * FROM draft_picks WHERE game_id = ? ORDER BY pick_number",
                (game_id,),
            ).fetchall()
        game = {
            "game_id": row["id"],
            "draft_year": row["draft_year"],
            "user_team": loads(row["user_team_json"]),
            "rounds": row["rounds"],
            "seed": row["seed"],
            "current_index": max(0, int(row["current_pick"]) - 1),
            "status": row["status"],
            "available_ids": loads(row["available_ids_json"], []),
            "draft_order": loads(row["draft_order_json"], []),
            "picks": [
                {
                    "overall": pick["pick_number"],
                    "round": pick["round"],
                    "pick_in_round": pick["pick_number"],
                    "team_id": normalize_team_abbr(pick["team_abbr"]),
                    "team_name": self._team_for_game({"draft_year": row["draft_year"]}, pick["team_abbr"])["name"],
                    "hidden_id": pick["hidden_player_id"],
                    "fake_name": pick["fake_name"],
                    "position": pick["position"],
                    "college_team": pick["college_team"],
                    "is_user_pick": bool(pick["made_by_user"]),
                }
                for pick in picks
            ],
        }
        return game


def get_game_service() -> DraftGameService:
    return DraftGameService()
