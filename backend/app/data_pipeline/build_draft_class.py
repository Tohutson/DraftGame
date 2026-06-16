import argparse
from typing import Any, Dict

from app.data_pipeline.common import processed_path, prospects_for_year, write_json
from app.data_sources.cfbd_client import CFBDClient, MissingCFBDAPIKey
from app.data_sources.nflverse_client import NFLVerseClient


def build_draft_class(draft_year: int, force: bool = False) -> Dict[str, Any]:
    nflverse = NFLVerseClient()
    cfbd = CFBDClient()

    nflverse.draft_picks([draft_year], force=force)
    cfbd_status = "skipped_missing_api_key"
    if cfbd.available:
        try:
            cfbd.player_season_stats(draft_year - 1)
            cfbd.teams(draft_year - 1)
            cfbd_status = "fetched_or_cached"
        except MissingCFBDAPIKey:
            cfbd_status = "skipped_missing_api_key"
        except Exception as exc:
            cfbd_status = f"partial_error: {exc}"

    prospects = prospects_for_year(draft_year)
    payload = {
        "draft_year": draft_year,
        "source": "processed_from_local_cache_with_external_raw_cache_when_available",
        "cfbd_status": cfbd_status,
        "prospects": prospects,
    }
    path = write_json(processed_path(f"draft_class_{draft_year}.json"), payload)
    return {"path": str(path), "prospect_count": len(prospects), "cfbd_status": cfbd_status}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-year", type=int, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    print(build_draft_class(args.draft_year, args.force))


if __name__ == "__main__":
    main()

