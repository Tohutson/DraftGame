# Hidden Name Draft

Hidden Name Draft is an NFL draft guessing/simulation game. During the draft, real historical prospects are shown with fake names and pre-NFL information only. After the draft is complete, the backend reveals the real players, actual NFL draft outcomes, career summaries, and a simple draft grade.

## Architecture

- `backend/`: FastAPI API, SQLite persistence, data build services, game logic, simulation, reveal logic, and anti-leak checks.
- `frontend/`: React UI for draft setup, data status, draft board, prospect details, simulation controls, and reveal results.
- `backend/app/data/draft_game.db`: persistent local SQLite database. This is the source of truth for game-ready data.

Normal gameplay reads from SQLite. External sources are used only to populate missing draft years.

## Data Flow

When a game starts for draft year `Y`:

1. `DraftYearDataService.ensure_draft_year_ready(Y)` checks SQLite for a complete or valid partial build.
2. If valid data already exists, the game starts immediately from database rows.
3. If data is missing or force rebuild is requested, the backend creates a `data_builds` row and fetches from:
   - `nflreadpy` / nflverse for NFL draft picks, rosters, player stats, IDs, and combine data when available.
   - CollegeFootballData.com for college stats, teams, conferences, and roster metadata when `CFBD_API_KEY` is set.
4. The backend normalizes and stores teams, rosters, team needs, prospects, fake names, college stats, draft results, career stats, public prospect views, and private reveal data in SQLite.
5. Validation marks the build `complete`, `partial`, or `failed`.
6. The game is created from database records.

Bundled CSVs, downloaded static CSVs, and processed JSON snapshots are not the normal source of truth. Sample/demo data must stay explicitly separate and must not be mixed into real builds.

## Environment

Copy `.env.example` as needed:

```bash
CFBD_API_KEY=
DATA_CACHE_DIR=backend/app/data
DATABASE_URL=sqlite:///backend/app/data/draft_game.db
DEFAULT_DRAFT_YEAR=2018
DEFAULT_RANDOM_SEED=42
ENABLE_ESPN_FALLBACK=false
REACT_APP_API_BASE=http://localhost:8000/api
```

`DATABASE_URL` is optional. If omitted, the backend uses `backend/app/data/draft_game.db`.

CollegeFootballData keys are available from https://collegefootballdata.com/. Without `CFBD_API_KEY`, draft years can still build from nflverse, but college stats are marked partial.

## Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```

Install `nflreadpy` in the backend environment if it is not already installed:

```bash
pip install nflreadpy
```

The SQLite schema is initialized on app startup. The database persists across server restarts.

## Frontend

```bash
cd frontend
npm install
npm start
```

Open `http://localhost:3000`.

The setup screen shows whether each selectable draft year is missing, partial, failed, or already built. Missing years are built when the user starts a draft.

## Data Build API

Build or force rebuild a draft year:

```bash
curl -X POST "http://localhost:8000/api/data/draft-years/2018/build?through_season=2025"
curl -X POST "http://localhost:8000/api/data/draft-years/2018/build?through_season=2025&force=true"
```

Inspect status:

```bash
curl "http://localhost:8000/api/data/status"
curl "http://localhost:8000/api/data/draft-years/2018/status"
curl "http://localhost:8000/api/data/draft-classes/2018/validation"
```

Useful endpoints:

- `GET /api/data/draft-years`
- `POST /api/data/draft-years/{draft_year}/build`
- `GET /api/data/draft-years/{draft_year}/status`
- `POST /api/games`
- `GET /api/games/{game_id}`
- `POST /api/games/{game_id}/pick`
- `POST /api/games/{game_id}/simulate-until-user-pick`
- `GET /api/games/{game_id}/draft-board`
- `GET /api/games/{game_id}/results`

## Data Sources

`nflreadpy` / nflverse provides:

- NFL draft results
- pre-draft rosters from season `draft_year - 1`
- NFL player stats and roster presence for career summaries
- player identifiers
- combine and physical data when exposed by the installed package version

CollegeFootballData provides:

- college player season stats
- college teams
- conferences
- college roster/player metadata when available

Every important persisted record carries a source label such as `nflverse`, `cfbd`, `computed`, `partial`, or `sample`. Validation fails builds that mix sample/fallback rows into real data.

## Anti-Leak Design

The backend owns all private player data. Active draft endpoints return only fake names, hidden IDs, position, college/team context, physical data, college stats, projection, and sanitized pre-draft fields.

Pre-reveal endpoints are checked against private fields such as `real_name`, `real_player_id`, actual NFL draft data, career summaries, career value, and outcome labels. Results endpoints reveal those fields only after the draft is complete.

## Tests

Backend tests mock external APIs and do not require live network calls:

```bash
cd backend
source venv/bin/activate
python -m pytest
```

Frontend build check:

```bash
cd frontend
npm run build
```

## Known Limitations

- Draft-year builds are synchronous for now. The build service is isolated so it can later move to a background job.
- Missing `CFBD_API_KEY` produces partial college data instead of failing the whole draft year.
- `nflreadpy` package APIs can vary by version; errors are surfaced as missing package, missing expected function, schema mismatch, API failure, or incomplete data where possible.
- There is no auth, cloud database, multiplayer, trading, or user account system.
