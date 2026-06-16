import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

function DraftSetup() {
    const [years, setYears] = useState([]);
    const [teams, setTeams] = useState([]);
    const [selectedYear, setSelectedYear] = useState("");
    const [selectedTeam, setSelectedTeam] = useState("");
    const [rounds, setRounds] = useState("");
    const [seed, setSeed] = useState(2026);
    const [dataStatus, setDataStatus] = useState(null);
    const [yearStatus, setYearStatus] = useState(null);
    const [loading, setLoading] = useState(true);
    const [startLoading, setStartLoading] = useState(false);
    const [error, setError] = useState(null);

    const navigate = useNavigate();

    const handleStartDraft = async () => {
        setStartLoading(true);
        setError(null);
        try {
            const game = await api.createGame({
                draft_year: Number(selectedYear),
                user_team: selectedTeam || null,
                rounds: rounds ? Number(rounds) : null,
                seed: Number(seed) || 2026,
            });
            navigate(`/draft/${game.game_id}`);
        } catch (err) {
            setError(err.message);
        } finally {
            setStartLoading(false);
        }
    };

    const statusForSelectedYear = () => {
        if (yearStatus && Number(yearStatus.draft_year) === Number(selectedYear)) {
            return yearStatus;
        }
        return years.find((year) => Number(year.draft_year) === Number(selectedYear)) || null;
    };

    useEffect(() => {
        let cancelled = false;
        async function load() {
            try {
                const [yearData, statusData] = await Promise.all([api.getYears(), api.getDataStatus()]);
                if (cancelled) return;
                const builtYears = yearData || [];
                const builtByYear = new Map(builtYears.map((year) => [Number(year.draft_year), year]));
                const optionYears = statusData.draft_year_options || [statusData.default_draft_year];
                const merged = optionYears.map((year) => (
                    builtByYear.get(Number(year)) || { draft_year: year, status: "missing" }
                ));
                setYears(merged);
                setDataStatus(statusData);
                const initial = merged[merged.length - 1]?.draft_year || statusData.default_draft_year || "";
                setSelectedYear(String(initial));
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
    }, []);

    useEffect(() => {
        if (!selectedYear) return;
        let cancelled = false;
        async function loadTeams() {
            try {
                const [teamData, status] = await Promise.all([
                    api.getTeams(selectedYear),
                    api.getYearStatus(selectedYear),
                ]);
                if (cancelled) return;
                setTeams(teamData);
                setSelectedTeam(teamData[0]?.id || "");
                setYearStatus(status);
            } catch (err) {
                if (!cancelled) setError(err.message);
            }
        }
        loadTeams();
        return () => {
            cancelled = true;
        };
    }, [selectedYear]);

    return (
        <main className="setup-page">
            <section className="setup-panel">
                <div>
                    <p className="eyebrow">NFL Draft Memory Game</p>
                    <h1>Hidden Name Draft</h1>
                    <p className="lede">
                        Draft college prospects using fake names, then reveal the real NFL players
                        and career outcomes after the final pick.
                    </p>
                </div>

                {error && <p className="error">{error}</p>}

                {dataStatus && (
                    <div className="data-status">
                        <strong>Database source</strong>
                        <span>{dataStatus.available_draft_years.length} built years</span>
                        <span>{dataStatus.prospect_count.toLocaleString()} prospects</span>
                        <span>{dataStatus.cfbd_configured ? "CFBD key configured" : "CFBD key missing"}</span>
                    </div>
                )}

                {selectedYear && (
                    <div className={`year-status ${statusForSelectedYear()?.status || "missing"}`}>
                        <strong>{selectedYear} data: {statusForSelectedYear()?.status || "missing"}</strong>
                        <span>
                            {(statusForSelectedYear()?.status || "missing") === "missing"
                                ? "The backend will fetch nflverse and CFBD data before starting."
                                : "Stored in the local SQLite database."}
                        </span>
                        {!dataStatus?.cfbd_configured && (
                            <span>College stats may be partial until CFBD_API_KEY is set.</span>
                        )}
                    </div>
                )}

                <label>
                    Draft class
                <select
                    value={selectedYear}
                    onChange={(e) => setSelectedYear(e.target.value)}
                        disabled={loading}
                >
                        {years.map((year) => (
                            <option key={year.draft_year} value={year.draft_year}>
                                {year.draft_year} ({year.status || "missing"})
                            </option>
                        ))}
                </select>
                </label>

                <label>
                    Your team
                <select
                    value={selectedTeam}
                    onChange={(e) => setSelectedTeam(e.target.value)}
                        disabled={loading}
                >
                        {teams.map((team) => (
                            <option key={team.id} value={team.id}>{team.name}</option>
                        ))}
                </select>
                </label>

                <div className="setup-grid">
                    <label>
                        Rounds
                        <select value={rounds} onChange={(e) => setRounds(e.target.value)}>
                            <option value="">Full Draft</option>
                            <option value="1">1</option>
                            <option value="3">3</option>
                            <option value="7">7</option>
                        </select>
                    </label>
                    <label>
                        Seed
                        <input value={seed} onChange={(e) => setSeed(e.target.value)} />
                    </label>
                </div>

            <button
                    className="primary"
                onClick={handleStartDraft}
                    disabled={!selectedYear || !selectedTeam || startLoading || loading}
            >
                    {startLoading
                        ? "Preparing..."
                        : (statusForSelectedYear()?.status === "complete" || statusForSelectedYear()?.status === "partial")
                            ? "Start Game"
                            : "Build and Start"}
            </button>
            </section>
        </main>
    );
}

export default DraftSetup;
