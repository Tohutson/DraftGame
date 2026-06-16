import json
import time
from pathlib import Path
from typing import Any, Dict

import httpx

from app.core.config import Settings, ensure_data_dirs, get_settings


class MissingCFBDAPIKey(RuntimeError):
    pass


class CFBDClient:
    BASE_URL = "https://api.collegefootballdata.com"

    def __init__(self, settings: Settings | None = None, timeout: float = 20.0):
        self.settings = settings or get_settings()
        self.timeout = timeout
        ensure_data_dirs(self.settings)
        self.cache_dir = self.settings.raw_dir / "cfbd"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return bool(self.settings.cfbd_api_key)

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-")
        return self.cache_dir / f"{safe}.json"

    def get(
        self,
        path: str,
        params: Dict[str, Any] | None = None,
        cache_key: str | None = None,
        force: bool = False,
    ) -> Any:
        if not self.available:
            raise MissingCFBDAPIKey("CFBD_API_KEY is not set; skipping CollegeFootballData fetch.")

        params = {k: v for k, v in (params or {}).items() if v is not None}
        key = cache_key or f"{path}_{json.dumps(params, sort_keys=True)}"
        cache_path = self._cache_path(key)
        if cache_path.exists() and not force:
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)

        headers = {"Authorization": f"Bearer {self.settings.cfbd_api_key}"}
        url = f"{self.BASE_URL}{path}"
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params, headers=headers)
                if response.status_code == 429:
                    time.sleep(2 + attempt)
                    continue
                response.raise_for_status()
                payload = response.json()
                with cache_path.open("w", encoding="utf-8") as handle:
                    json.dump(payload, handle, indent=2)
                return payload
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                last_error = exc
                time.sleep(1 + attempt)

        raise RuntimeError(f"CFBD request failed for {path}: {last_error}")

    def player_season_stats(self, year: int) -> Any:
        return self.get("/stats/player/season", {"year": year}, f"player_season_stats_{year}")

    def rosters(self, year: int) -> Any:
        return self.get("/roster", {"year": year}, f"rosters_{year}")

    def teams(self, year: int) -> Any:
        return self.get("/teams/fbs", {"year": year}, f"teams_{year}")


# Backward-compatible helpers for older imports.
def get_api_key() -> str | None:
    return get_settings().cfbd_api_key


def client_available() -> bool:
    return CFBDClient().available

