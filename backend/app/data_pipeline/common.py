import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import ensure_data_dirs, get_settings


def load_unified_dataset() -> Dict[str, Any]:
    from app.data_loader import DEFAULT_DATA_FILE

    with DEFAULT_DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def processed_path(name: str) -> Path:
    settings = get_settings()
    ensure_data_dirs(settings)
    return settings.processed_dir / name


def prospects_for_year(draft_year: int) -> List[Dict[str, Any]]:
    from app.data_loader import DataLoader

    return DataLoader().prospects_for_year(draft_year)
