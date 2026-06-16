import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";

function DraftSetup() {
    const [years, setYears] = useState([]);
    const [teams, setTeams] = useState([]);
    const [selectedYear, setSelectedYear] = useState("");
    const [selectedTeam, setSelectedTeam] = useState("");
    const [rounds, setRounds] = useState(3);
    const [seed, setSeed] = useState(2026);
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
                rounds: Number(rounds),
                seed: Number(seed) || 2026,
            });
            navigate(`/draft/${game.game_id}`);
        } catch (err) {
            setError(err.message);
        } finally {
            setStartLoading(false);
        }
    };

    useEffect(() => {
        let cancelled = false;
        async function load() {
            try {
                const [yearData, teamData] = await Promise.all([api.getYears(), api.getTeams()]);
                if (cancelled) return;
                setYears(yearData);
                setTeams(teamData);
                setSelectedYear(String(yearData[yearData.length - 1] || ""));
                setSelectedTeam(teamData[0]?.id || "");
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

                <label>
                    Draft class
                <select
                    value={selectedYear}
                    onChange={(e) => setSelectedYear(e.target.value)}
                        disabled={loading}
                >
                        {years.map((year) => (
                            <option key={year} value={year}>{year}</option>
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
                            <option value={1}>1</option>
                            <option value={3}>3</option>
                            <option value={7}>7</option>
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
                    {startLoading ? "Starting..." : "Start Game"}
            </button>
            </section>
        </main>
    );
}

export default DraftSetup;
