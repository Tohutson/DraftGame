# AGENTS.md

## Project Goal

This project is an NFL draft guessing/simulation game.

The user selects a draft year and drafts real historical NFL prospects without seeing their real names. During the draft, players are shown with fake names, college stats, physical/combine info, and team context. After the draft, the game reveals the real players, their actual NFL draft slots, and their NFL career outcomes.

The system should be simple, modular, robust, and easy to run locally.

## Current Architecture Goal

Use:

- FastAPI backend
- React frontend
- Persistent SQLite database for local development
- `nflreadpy` / nflverse as the NFL data source
- CollegeFootballData.com as the college football data source

The database is the source of truth for game-ready data.

External data sources should populate the database. The game should read from the database, not from scattered CSVs, JSON files, or temporary local caches.

## Data Flow

When a user selects a draft year and starts a game:

1. Check the persistent database for that draft year.
2. If the draft year exists and has valid complete or partial data, use it.
3. If the draft year is missing, fetch the needed data from:
   - `nflreadpy` / nflverse
   - CollegeFootballData.com

4. Normalize the data.
5. Store it in the database.
6. Validate it.
7. Start the game.

Do not use bundled local CSVs as the normal source of truth.

Sample or fallback data is allowed only for clearly marked demo/test mode. It must never be silently mixed with real data or presented as real.

## Coding Principles

Write code that is:

- Simple
- Modular
- Readable
- Easy to debug
- Easy to test
- Resistant to partial/missing external data

Prefer clear service boundaries over clever abstractions.

Good backend service boundaries include:

- `DraftYearDataService`
- `NflverseDataService`
- `CollegeFootballDataService`
- `DataNormalizationService`
- `TeamNeedsService`
- `CareerStatsService`
- `ValidationService`
- `DraftGameService`
- `RevealService`

Keep game logic on the backend.

The frontend should focus on displaying state clearly and sending user actions to the backend.

## Data Source Rules

Use only these primary data sources:

1. `nflreadpy` / nflverse
2. CollegeFootballData.com

Do not add paid APIs.

Do not scrape websites as a core dependency.

Do not rely on static downloaded CSVs as the main source of truth.

Every important data record should track its source, such as:

- `nflverse`
- `cfbd`
- `computed`
- `partial`
- `sample`

Data source labels must be honest. Do not mark top-level data as real if the underlying records are fallback/sample.

## Anti-Leak Rule

Before the draft is complete, never expose:

- real player name
- real player ID
- actual NFL draft slot
- actual NFL team
- NFL career stats
- career value
- outcome label

During the draft, the frontend should only receive fake names and pre-NFL information.

Real identities and career outcomes should only be returned by the reveal/results endpoint after the draft is complete.

## UI Goals

The UI should be simple and information-focused.

Prioritize:

- readability
- clear draft board
- clear team needs
- clear current pick/team on clock
- easy prospect comparison
- simple reveal screen

Avoid heavy UI libraries unless already used.

Basic colors and clean spacing are enough.

## Database Rules

Use a persistent SQLite database for local development.

The database should persist across server restarts.

Do not rebuild a draft year every time the app starts.

Add force-rebuild behavior when needed.

If migrations are already set up, use them. If not, provide a simple table initialization path.

## Testing Expectations

Add or update tests for meaningful behavior.

Important tests:

- database initializes correctly
- draft year lookup checks DB first
- missing draft year triggers data build
- existing valid draft year does not refetch
- force rebuild works
- team abbreviation normalization is consistent
- pre-reveal endpoints do not leak private fields
- reveal endpoint only exposes real data after draft completion
- game can be completed end to end
- data source consistency validation catches mixed real/sample data

Mock external APIs in tests. Do not require live API calls for tests.

## Error Handling

External data can be incomplete.

Handle missing data gracefully.

Do not crash when optional fields are missing.

Do not hide real errors behind misleading messages like “package not installed” unless the package truly cannot be imported.

Use specific error messages for:

- missing `nflreadpy`
- missing `CFBD_API_KEY`
- API failure
- missing expected function
- schema mismatch
- failed player matching
- incomplete data

## README Updates

Whenever data flow, setup, commands, or dependencies change, update the README.

The README should explain:

- how to install dependencies
- how to set `CFBD_API_KEY`
- where the SQLite DB lives
- how to build a draft year
- how to force rebuild
- how to run backend
- how to run frontend
- how to run tests
- what data comes from nflreadpy
- what data comes from CollegeFootballData
- known limitations

## Commit Instructions

Commit work in small, logical chunks.

Good commit examples:

- `Add persistent draft year database models`
- `Replace CSV draft loader with database-backed service`
- `Add nflreadpy roster ingestion`
- `Add CFBD college stats ingestion`
- `Implement draft year build status API`
- `Prevent real player data leaks before reveal`
- `Add tests for database-backed draft flow`
- `Update README for new data pipeline`

Before committing:

1. Run backend tests.
2. Run frontend build or lint if available.
3. Confirm the app still starts.
4. Confirm no private reveal data leaks before draft completion.
5. Update README if setup or behavior changed.

Do not commit broken intermediate states unless explicitly asked.

## Development Priority

When making changes, prioritize:

1. App runs locally.
2. Data flow is consistent and database-backed.
3. Draft year builds are persistent.
4. The game is playable end to end.
5. Real identities stay hidden until reveal.
6. Code is simple and testable.
7. README accurately reflects reality.

Avoid overbuilding cloud, auth, multiplayer, or advanced scouting models until the core game and data flow are stable.
