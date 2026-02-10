import { useParams } from "react-router-dom";

export default function DraftBoard() {
    const { draftId } = useParams(); // grab draftId from URL

    return (
        <div>
            <h1>Draft Board</h1>
            <p>Draft ID: {draftId}</p>
            {/* Later: fetch draft status and available players */}
        </div>
    );
}
