import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import get_settings
from app.data_pipeline.common import prospects_for_year
from app.services.prospect_service import assert_no_private_fields, public_prospect
from app.team_abbreviations import normalize_team_abbr


REQUIRED_FIELDS = [
    "hidden_id",
    "real_player_id",
    "real_name",
    "fake_name",
    "draft_year",
    "rank",
    "position",
    "college_team",
    "actual_draft",
    "career_summary",
    "career_value",
]


def validate_prospect(prospect: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_FIELDS:
        if prospect.get(field) in (None, "", []):
            errors.append(f"{prospect.get('hidden_id', '<unknown>')}: missing {field}")
    draft = prospect.get("actual_draft") or {}
    for field in ("year", "round", "pick", "overall", "team"):
        if draft.get(field) in (None, ""):
            errors.append(f"{prospect.get('hidden_id', '<unknown>')}: missing actual_draft.{field}")
    if prospect.get("real_name") == prospect.get("fake_name"):
        errors.append(f"{prospect.get('hidden_id', '<unknown>')}: fake name matches real name")
    return errors


def validate_dataset(draft_year: int) -> Dict[str, Any]:
    prospects = prospects_for_year(draft_year)
    errors: List[str] = []
    warnings: List[str] = []
    if not prospects:
        errors.append(f"No prospects found for {draft_year}")
    seen = set()
    for prospect in prospects:
        hidden_id = prospect.get("hidden_id")
        if hidden_id in seen:
            errors.append(f"Duplicate hidden_id {hidden_id}")
        seen.add(hidden_id)
        errors.extend(validate_prospect(prospect))
        if not prospect.get("college_stats"):
            warnings.append(f"{hidden_id}: no college stats")
        if not prospect.get("scouting_report"):
            warnings.append(f"{hidden_id}: no scouting report")
    processed_errors, processed_warnings = validate_processed_data(draft_year, prospects)
    errors.extend(processed_errors)
    warnings.extend(processed_warnings)
    return {
        "draft_year": draft_year,
        "prospect_count": len(prospects),
        "valid": not errors,
        "errors": errors,
        "warnings": warnings[:200],
        "warning_count": len(warnings),
    }


def _career_stats_path(draft_year: int) -> Path | None:
    processed_dir = get_settings().processed_dir
    candidates = sorted(
        processed_dir.glob(f"career_stats_{int(draft_year)}_through_*.json"),
        key=lambda path: int(re.search(r"_through_(\d+)\.json$", path.name).group(1)) if re.search(r"_through_(\d+)\.json$", path.name) else 0,
    )
    return candidates[-1] if candidates else None


def validate_processed_data(draft_year: int, prospects: List[Dict[str, Any]]) -> tuple[List[str], List[str]]:
    errors: List[str] = []
    warnings: List[str] = []
    career_path = _career_stats_path(draft_year)
    if career_path:
        try:
            with career_path.open("r", encoding="utf-8") as handle:
                career_payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"career stats cache unreadable: {exc}")
            career_payload = {}
        players = career_payload.get("players", {})
        real_mode = career_payload.get("source") == "nflverse"
        source_counts: Dict[str, int] = {}
        for player in players.values():
            source = player.get("career_data_source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1
        if real_mode and players and source_counts.get("fallback_sample", 0) == len(players):
            errors.append("career stats source is nflverse but every player is fallback_sample")
        if career_payload.get("source_counts") and career_payload.get("source_counts") != source_counts:
            errors.append("career stats top-level source_counts does not match player-level career_data_source counts")
        for prospect in prospects:
            player = players.get(str(prospect.get("real_player_id")))
            if not player:
                warnings.append(f"{prospect.get('hidden_id')}: no processed career stats entry")
                continue
            if not player.get("career_data_source") or not player.get("career_data_quality"):
                errors.append(f"{prospect.get('hidden_id')}: career stats missing source/quality marker")
            if real_mode and player.get("career_data_source") == "fallback_sample":
                warnings.append(f"{prospect.get('hidden_id')}: nflverse build fell back to sample career data")
            elif player.get("career_data_source") == "partial_nflverse":
                warnings.append(f"{prospect.get('hidden_id')}: partial nflverse career data")
            if player.get("career_data_source") != "fallback_sample" and player.get("career_value") in (None, ""):
                errors.append(f"{prospect.get('hidden_id')}: real career stats missing career_value")
    else:
        warnings.append("No processed career stats file found; sample fallback career data will be used.")

    needs_path = get_settings().processed_dir / f"team_needs_{int(draft_year) - 1}.json"
    if needs_path.exists():
        try:
            with needs_path.open("r", encoding="utf-8") as handle:
                needs_payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"team needs cache unreadable: {exc}")
            needs_payload = {}
        raw_teams = needs_payload.get("teams", {})
        teams = {normalize_team_abbr(team_id): rows for team_id, rows in raw_teams.items()}
        duplicate_aliases = {}
        for team_id in raw_teams:
            canonical = normalize_team_abbr(team_id)
            duplicate_aliases.setdefault(canonical, []).append(team_id)
        duplicate_aliases = {team: aliases for team, aliases in duplicate_aliases.items() if len(set(aliases)) > 1}
        if duplicate_aliases:
            errors.append(f"team needs contain duplicate abbreviation aliases: {duplicate_aliases}")
        alias_mismatches = sorted(
            f"{team_id}->{normalize_team_abbr(team_id)}"
            for team_id in raw_teams
            if team_id != normalize_team_abbr(team_id)
        )
        if alias_mismatches:
            errors.append(f"team needs use non-canonical abbreviations: {', '.join(alias_mismatches)}")
        expected_teams = {
            normalize_team_abbr(prospect.get("actual_draft", {}).get("team"))
            for prospect in prospects
            if prospect.get("actual_draft", {}).get("team")
        }
        missing_teams = sorted(team for team in expected_teams if team not in teams)
        if missing_teams:
            errors.append(f"team needs missing teams for pre-draft season: {', '.join(missing_teams[:20])}")
        for team_id, rows in teams.items():
            for row in rows:
                if "need_score" not in row and "score" not in row:
                    errors.append(f"{team_id}: team need row missing need_score")
                if not row.get("data_source") or not row.get("data_quality"):
                    message = f"{team_id}: team need row missing source/quality marker"
                    if needs_payload.get("source") == "nflverse":
                        errors.append(message)
                    else:
                        warnings.append(message)
    else:
        warnings.append("No processed team needs file found; sample team needs will be used.")

    try:
        for prospect in prospects[:10]:
            assert_no_private_fields(public_prospect(prospect))
    except AssertionError as exc:
        errors.append(f"Public prospect payload leaks reveal data before draft completion: {exc}")
    return errors, warnings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draft-year", type=int, required=True)
    args = parser.parse_args()
    result = validate_dataset(args.draft_year)
    print(result)
    if not result["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
