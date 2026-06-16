import argparse
from typing import Any, Dict

from app.data_pipeline.build_draft_class import build_draft_class
from app.data_pipeline.build_nfl_career_stats import build_nfl_career_stats
from app.data_pipeline.build_player_id_map import build_player_id_map
from app.data_pipeline.build_team_needs import build_team_needs
from app.data_pipeline.build_team_rosters import build_team_rosters
from app.data_pipeline.validate_dataset import validate_dataset
from app.scripts.build_sample_dataset import main as build_local_cache


def build_all(draft_year: int, through_season: int = 2025, force: bool = False) -> Dict[str, Any]:
    build_local_cache()
    season = draft_year - 1
    result = {
        "draft_year": draft_year,
        "team_rosters": build_team_rosters(season, force),
        "team_needs": build_team_needs(season),
        "draft_class": build_draft_class(draft_year, force),
        "career_stats": build_nfl_career_stats(draft_year, through_season, force),
        "player_id_map": build_player_id_map(draft_year),
        "validation": validate_dataset(draft_year),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-year", type=int, required=True)
    parser.add_argument("--through-season", type=int, default=2025)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(build_all(args.draft_year, args.through_season, args.force))


if __name__ == "__main__":
    main()

