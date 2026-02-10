import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

export default function DraftBoard() {
    const { draftId } = useParams(); // grab draftId from URL

    const [boardData, setBoardData] = useState({ year: null, current_index: null, board: [] });
    const [boardLoading, setBoardLoading] = useState(false);
    const [boardError, setBoardError] = useState(null);

    useEffect(() => {
        let isCancelled = false;

        const fetchBoard = async () => {
            setBoardLoading(true);
            setBoardError(null);

            try {
                const response = await fetch(`http://localhost:8000/draft/${draftId}/board`);

                if (!response.ok) {
                    throw new Error("Failed to load draft board");
                }

                const data = await response.json();

                if (!isCancelled) {
                    setBoardData(data);
                    console.log(data);
                }
            } catch (err) {
                if (!isCancelled) {
                    setBoardError(err.message);
                }
            } finally {
                if (!isCancelled) {
                    setBoardLoading(false)
                }
            }
        };

        fetchBoard();

        return () => {
            isCancelled = true;
        };
    }, [draftId]);

    const { year, current_index, board } = boardData;

    return (
        <div>
            <h2>Draft Board {year}</h2>
            <p>Current Pick Index: {current_index}</p>
            <table style={{ borderCollapse: "collapse", width: "100%" }}>
                <thead>
                    <tr>
                        <th style={{ border: "1px solid #ccc", padding: "8px" }}>Overall</th>
                        <th style={{ border: "1px solid #ccc", padding: "8px" }}>Round</th>
                        <th style={{ border: "1px solid #ccc", padding: "8px" }}>Pick</th>
                        <th style={{ border: "1px solid #ccc", padding: "8px" }}>Team</th>
                        <th style={{ border: "1px solid #ccc", padding: "8px" }}>Player ID</th>
                    </tr>
                </thead>
                <tbody>
                    {board.map((pick) => (
                        <tr key={pick.overall}>
                            <td style={{ border: "1px solid #ccc", padding: "8px" }}>{pick.overall}</td>
                            <td style={{ border: "1px solid #ccc", padding: "8px" }}>{pick.round}</td>
                            <td style={{ border: "1px solid #ccc", padding: "8px" }}>{pick.pick}</td>
                            <td style={{ border: "1px solid #ccc", padding: "8px" }}>{pick.team}</td>
                            <td style={{ border: "1px solid #ccc", padding: "8px" }}>{pick.player_id}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

