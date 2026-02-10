import { useEffect, useState } from "react";

function DraftSetup() {
    const [years, setYears] = useState([])
    const [teams, setTeams] = useState([])

    const [yearsLoading, setYearsLoading] = useState(false);
    const [teamsLoading, setTeamsLoading] = useState(false);

    const [yearsError, setYearsError] = useState(null);
    const [teamsError, setTeamsError] = useState(null);

    const [selectedYear, setSelectedYear] = useState("");
    const [selectedTeam, setSelectedTeam] = useState("");

    const [startLoading, setStartLoading] = useState(false);
    const [startError, setStartError] = useState(null);

    const handleStartDraft = () => {
        setStartLoading(true);
        setStartError(null);

        fetch("http://localhost:8000/draft/start", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                year: Number(selectedYear),
                user_team: selectedTeam,
            }),
        })
            .then((res) => {
                if (!res.ok) throw new Error("Failed to start draft");
                return res.json();
            })
            .then((data) => {
                console.log("Draft started: ", data);
            })
            .catch((err) => setStartError(err.message))
            .finally(() => setStartLoading(false));
    };

    useEffect(() => {
        setYearsLoading(true);
        setYearsError(null);

        fetch("http://localhost:8000/draft/years")
            .then((res) => {
                if (!res.ok) throw new Error("Failed to load years");
                return res.json();
            })
            .then((data) => setYears(data))
            .catch((err) => setYearsError(err.message))
            .finally(() => setYearsLoading(false));
    }, []);

    useEffect(() => {
        if (!selectedYear) return;

        setTeamsLoading(true);
        setTeamsError(null);

        fetch(`http://localhost:8000/draft/teams?year=${selectedYear}`)
            .then((res) => {
                if (!res.ok) throw new Error("Failed to load teams");
                return res.json();
            })
            .then((data) => setTeams(data))
            .catch((err) => setTeamsError(err.message))
            .finally(() => setTeamsLoading(false));
    }, [selectedYear]);

    useEffect(() => {
        setSelectedTeam("");
    }, [selectedYear]);

    return (
        <div style={{ padding: "2rem" }}>
            <h1>Draft Setup</h1>

            <div>
                <label>Year:</label>
                <select
                    value={selectedYear}
                    onChange={(e) => setSelectedYear(e.target.value)}
                    disabled={yearsLoading}
                >
                    {yearsLoading ? (
                        <option>Loading years...</option>
                    ) : (
                        <>
                            <option value="">Select a year</option>
                            {years.map((year) => (
                                <option key={year} value={year}>
                                    {year}
                                </option>
                            ))}
                        </>
                    )}
                </select>
                {yearsError && (
                    <p style={{ color: "red", marginTop: "0.5rem" }}>
                        {yearsError}
                    </p>
                )}
            </div>

            <div>
                <label>Team:</label>
                <select
                    value={selectedTeam}
                    onChange={(e) => setSelectedTeam(e.target.value)}
                    disabled={!selectedYear || teamsLoading}
                >
                    {!selectedYear ? (
                        <option>Select a year first</option>
                    ) : teamsLoading ? (
                        <option>Loading teams...</option>
                    ) : (
                        <>
                            <option value="">Select a team</option>
                            {teams.map((team) => (
                                <option key={team} value={team}>
                                    {team}
                                </option>
                            ))}
                        </>
                    )}
                </select>
                {teamsError && (
                    <p style={{ color: "red", marginTop: "0.5rem" }}>
                        {teamsError}
                    </p>
                )}
            </div>

            <button
                onClick={handleStartDraft}
                disabled={!selectedYear || !selectedTeam || startLoading}
            >
                {startLoading ? "Starting..." : "Start Draft"}
            </button>
            {startError && (
                <p style={{ color: "red", marginTop: "0.5rem" }}>
                    {startError}
                </p>
            )}
        </div>
    );
}

export default DraftSetup;
