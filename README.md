# Hidden Name Draft

A playable NFL draft game where real historical prospects are shown with fake names until the draft is complete. The backend owns game state, simulation, and reveal logic so real player identities and career outcomes are not sent to the frontend during active gameplay.

## Architecture

- `backend/`: FastAPI API, draft simulation services, reveal/grading logic, cached data loading, and data-build scripts.
- `frontend/`: React app for setup, draft board, prospect details, team needs, pick history, and final reveal.
- `backend/app/data/sample_game_data.json`: bundled offline sample dataset generated from the existing prospect CSVs.

## Setup

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm start
```

The React app defaults to `http://localhost:8000/api`. To override it, create `frontend/.env` with:

```bash
REACT_APP_API_BASE=http://localhost:8000/api
```

## Rebuild Sample Data

The app runs without API keys using bundled sample data:

```bash
cd backend
source venv/bin/activate
python -m app.scripts.build_sample_dataset
```

The current bundled CSVs only include draft prospect data through 2021, so the sample game uses the 2021 draft class.

## Full Data Pipeline

Future full-data ingestion should be added behind cached build scripts, not live gameplay calls:

- NFL career data: use `nflreadpy` / nflverse in `backend/app/data_sources/nflverse_client.py`.
- College stats: use CollegeFootballData in `backend/app/data_sources/college_football_data_client.py`.
- Output cached JSON or parquet files under `backend/app/data/`.

CollegeFootballData key:

```bash
export COLLEGE_FOOTBALL_DATA_API_KEY=your_key_here
```

Gameplay should continue to work when this key is absent.

## Tests

```bash
cd backend
source venv/bin/activate
pytest
```

## Known Limitations

- The MVP sample dataset uses deterministic sample career summaries for offline play; the code includes stubs for replacing this with cached nflreadpy/nflverse career summaries.
- No authentication, multiplayer, trades, or database persistence.
- Completed draft results are kept in backend memory for the running process.
- Team needs are simple static lists that update when a team drafts a need position.

