"""
Build the full cached draft dataset.

This script is intentionally conservative in the MVP. It documents the target
entry point for combining CollegeFootballData college production, nflreadpy
career summaries, and the existing prospect CSVs into app/data/draft_classes.*
without making gameplay depend on network calls.
"""


def main() -> None:
    raise SystemExit(
        "Full dataset import is not implemented yet. Use "
        "`python -m app.scripts.build_sample_dataset` to rebuild the bundled sample."
    )


if __name__ == "__main__":
    main()

