import argparse
from typing import Any, Dict

from app.data_pipeline.common import processed_path, prospects_for_year, write_json


def build_player_id_map(draft_year: int) -> Dict[str, Any]:
    mapping = {
        prospect["hidden_id"]: {
            "real_player_id": prospect["real_player_id"],
            "real_name": prospect["real_name"],
            "draft_year": draft_year,
        }
        for prospect in prospects_for_year(draft_year)
    }
    path = write_json(processed_path(f"player_id_map_{draft_year}.json"), {"draft_year": draft_year, "players": mapping})
    return {"path": str(path), "player_count": len(mapping)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-year", type=int, required=True)
    args = parser.parse_args()
    print(build_player_id_map(args.draft_year))


if __name__ == "__main__":
    main()

