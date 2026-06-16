import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATA_FILE = DATA_DIR / "sample_game_data.json"


class DataLoader:
    def __init__(self, data_file: Path = DEFAULT_DATA_FILE):
        self.data_file = data_file
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        with self.data_file.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def teams(self) -> List[Dict[str, Any]]:
        return list(self._data.get("teams", []))

    def draft_years(self) -> List[int]:
        years = {int(p["draft_year"]) for p in self._data.get("prospects", [])}
        return sorted(years)

    def prospects_for_year(self, year: int) -> List[Dict[str, Any]]:
        prospects = [
            dict(p) for p in self._data.get("prospects", []) if int(p["draft_year"]) == int(year)
        ]
        return sorted(prospects, key=lambda p: int(p.get("rank", 9999)))

    def team_by_id(self, team_id: str) -> Optional[Dict[str, Any]]:
        team_id = team_id.upper()
        return next((t for t in self.teams() if t["id"].upper() == team_id), None)

    def prospect_by_hidden_id(self, hidden_id: str) -> Optional[Dict[str, Any]]:
        return next((p for p in self._data.get("prospects", []) if p["hidden_id"] == hidden_id), None)


@lru_cache(maxsize=1)
def get_data_loader() -> DataLoader:
    return DataLoader()

