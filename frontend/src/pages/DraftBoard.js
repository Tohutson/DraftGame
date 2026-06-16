import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

function statLine(stats = {}) {
  const entries = Object.entries(stats).slice(0, 3);
  if (!entries.length) return "Not available";
  return entries.map(([key, value]) => `${key}: ${value}`).join(" | ");
}

function physicalLine(player) {
  const parts = [];
  if (player.height) parts.push(`${player.height} in`);
  if (player.weight) parts.push(`${player.weight} lb`);
  return parts.length ? parts.join(" / ") : "Not available";
}

export default function DraftBoard() {
  const { draftId } = useParams();
  const [state, setState] = useState(null);
  const [board, setBoard] = useState([]);
  const [selected, setSelected] = useState(null);
  const [reveal, setReveal] = useState(null);
  const [position, setPosition] = useState("ALL");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("rank");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async (nextState = null) => {
    const loadedState = nextState || (await api.getGame(draftId));
    setState(loadedState);
    if (loadedState.status === "complete") {
      const result = await api.reveal(draftId);
      setReveal(result);
      setBoard([]);
      return;
    }
    const boardData = await api.getBoard(draftId);
    setBoard(boardData.prospects);
    setSelected((current) => {
      if (current && boardData.prospects.some((player) => player.hidden_id === current.hidden_id)) {
        return current;
      }
      return boardData.prospects[0] || null;
    });
  }, [draftId]);

  const simulateIfNeeded = useCallback(async (gameState) => {
    if (gameState.status === "active" && !gameState.is_user_on_clock) {
      return api.simulate(draftId);
    }
    return gameState;
  }, [draftId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const initial = await api.getGame(draftId);
        const next = await simulateIfNeeded(initial);
        if (!cancelled) await refresh(next);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [draftId, refresh, simulateIfNeeded]);

  const positions = useMemo(() => {
    return ["ALL", ...Array.from(new Set(board.map((p) => p.position))).sort()];
  }, [board]);

  const filtered = useMemo(() => {
    const query = search.trim().toLowerCase();
    const visible = board.filter((player) => {
      const matchesPosition = position === "ALL" || player.position === position;
      const matchesSearch = !query || player.fake_name.toLowerCase().includes(query);
      return matchesPosition && matchesSearch;
    });
    return [...visible].sort((a, b) => {
      if (sort === "position") return a.position.localeCompare(b.position) || a.rank - b.rank;
      if (sort === "need") {
        const needs = new Set(state?.team_needs || []);
        return Number(needs.has(b.position)) - Number(needs.has(a.position)) || a.rank - b.rank;
      }
      return a.rank - b.rank;
    });
  }, [board, position, search, sort, state]);

  async function choosePlayer(player) {
    setSelected(player);
    try {
      const details = await api.getProspect(draftId, player.hidden_id);
      setSelected(details);
    } catch {
      setSelected(player);
    }
  }

  async function makePick() {
    if (!selected || !state?.is_user_on_clock) return;
    setBusy(true);
    setError(null);
    try {
      const afterPick = await api.makePick(draftId, selected.hidden_id);
      const afterSim = await simulateIfNeeded(afterPick);
      setSelected(null);
      await refresh(afterSim);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function simulateRest() {
    setBusy(true);
    setError(null);
    try {
      const completed = await api.simulateRest(draftId);
      setSelected(null);
      await refresh(completed);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <main className="app-shell"><p>Loading draft...</p></main>;
  if (error && !state) return <main className="app-shell"><p className="error">{error}</p></main>;

  if (reveal) {
    return (
      <main className="app-shell">
        <div className="topbar">
          <div>
            <p className="eyebrow">Reveal</p>
            <h1>{reveal.user_team.name} Draft Grade: {reveal.grade}</h1>
            <p>{reveal.summary}</p>
          </div>
          <Link className="button-link" to="/">Restart</Link>
        </div>

        <section className="results-grid">
          {reveal.user_picks.map((pick) => (
            <article className="result-card" key={pick.overall}>
              <p className="pick-label">Pick {pick.overall} | {pick.position}</p>
              <h2>{pick.fake_name} was {pick.real_name}</h2>
              <p>{pick.outcome_label} | Value delta {pick.value_delta}</p>
              <p>{pick.reveal_blurb}</p>
              {pick.career_data_source && (
                <p className="data-source">
                  Career data: {pick.career_data_source} - {pick.career_data_quality}
                </p>
              )}
              <dl>
                {Object.entries(pick.career_summary || {}).map(([key, value]) => (
                  <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd>{value}</dd></div>
                ))}
              </dl>
            </article>
          ))}
        </section>

        <section className="missed">
          <h2>Best Players You Missed</h2>
          <table>
            <thead><tr><th>Fake Name</th><th>Real Name</th><th>Pos</th><th>College</th><th>Outcome</th></tr></thead>
            <tbody>
              {reveal.best_players_missed.map((player) => (
                <tr key={player.hidden_id}>
                  <td>{player.fake_name}</td>
                  <td>{player.real_name}</td>
                  <td>{player.position}</td>
                  <td>{player.college_team}</td>
                  <td>{player.outcome_label}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </main>
    );
  }

  const current = state?.current_pick;

  return (
    <main className="app-shell">
      <header className="draft-header">
        <div>
          <p className="eyebrow">Round {current?.round} | Pick {current?.overall}</p>
          <h1>{current?.team_name} on the clock</h1>
          <p>Your team: {state?.user_team.name} | Full draft: {state?.rounds} rounds</p>
        </div>
        <div className="header-actions">
          <button onClick={simulateRest} disabled={busy}>Sim Rest</button>
          <div className={state?.is_user_on_clock ? "clock user" : "clock"}>
            {state?.is_user_on_clock ? "Make your pick" : "Simulating"}
          </div>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="draft-layout">
        <div className="board-panel">
          <div className="controls">
            <input
              placeholder="Search fake name"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select value={position} onChange={(e) => setPosition(e.target.value)}>
              {positions.map((pos) => <option key={pos} value={pos}>{pos}</option>)}
            </select>
            <select value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="rank">Rank</option>
              <option value="position">Position</option>
              <option value="need">Team need</option>
            </select>
          </div>

          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Fake Name</th>
                <th>Pos</th>
                <th>College</th>
                <th>Stats</th>
                <th>Physical</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((player) => (
                <tr
                  key={player.hidden_id}
                  className={selected?.hidden_id === player.hidden_id ? "selected clickable" : "clickable"}
                  onClick={() => choosePlayer(player)}
                >
                  <td>{player.rank}</td>
                  <td>{player.fake_name}</td>
                  <td>{player.position}</td>
                  <td>{player.college_team}</td>
                  <td>{statLine(player.college_stats)}</td>
                  <td>{physicalLine(player)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="side-panel">
          <section>
            <h2>Team Needs</h2>
            {state?.team_needs_source && (
              <p className="data-source">Needs source: {state.team_needs_source}</p>
            )}
            <div className="need-list">
              {(state?.team_needs || []).map((need) => <span key={need}>{need}</span>)}
            </div>
          </section>

          <section>
            <h2>Prospect Detail</h2>
            {selected ? (
              <div className="detail">
                <h3>{selected.fake_name}</h3>
                <p>{selected.position} | {selected.college_team}</p>
                <p>{selected.scouting_blurb}</p>
                {selected.scouting_report?.length ? (
                  <div className="scouting-report">
                    <h3>Scouting Report</h3>
                    {selected.scouting_report.map((paragraph, index) => (
                      <p key={index}>{paragraph}</p>
                    ))}
                  </div>
                ) : null}
                <p><strong>College:</strong> {statLine(selected.college_stats)}</p>
                <p><strong>Physical:</strong> {physicalLine(selected)}</p>
                <button className="primary" disabled={!state?.is_user_on_clock || busy} onClick={makePick}>
                  {busy ? "Submitting..." : "Draft Player"}
                </button>
              </div>
            ) : <p>Select a prospect.</p>}
          </section>

          <section>
            <h2>Draft History</h2>
            <ol className="history">
              {state?.picks.slice(-12).map((pick) => (
                <li key={pick.overall}>
                  <span>{pick.overall}. {pick.team_id}</span>
                  <strong>{pick.fake_name}</strong>
                  <span>{pick.position}</span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </section>
    </main>
  );
}
