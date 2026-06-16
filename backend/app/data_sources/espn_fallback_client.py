import json
from pathlib import Path
from typing import Any

import httpx

from app.core.config import Settings, ensure_data_dirs, get_settings


class ESPNFallbackDisabled(RuntimeError):
    pass


class ESPNFallbackClient:
    BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

    def __init__(self, settings: Settings | None = None, timeout: float = 15.0):
        self.settings = settings or get_settings()
        self.timeout = timeout
        ensure_data_dirs(self.settings)
        self.cache_dir = self.settings.raw_dir / "espn"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-")
        return self.cache_dir / f"{safe}.json"

    def get(self, path: str, cache_key: str | None = None, force: bool = False) -> Any:
        if not self.settings.enable_espn_fallback:
            raise ESPNFallbackDisabled("ENABLE_ESPN_FALLBACK is false; ESPN fallback is disabled.")
        key = cache_key or path
        cache_path = self._cache_path(key)
        if cache_path.exists() and not force:
            with cache_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.BASE_URL}{path}")
            response.raise_for_status()
            payload = response.json()
        with cache_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return payload

