import { Routes, Route } from "react-router-dom";
import DraftSetup from "./pages/DraftSetup";
import DraftBoard from "./pages/DraftBoard";

function App() {
  return (
    <Routes>
      <Route path="/" element={<DraftSetup />} />
      <Route path="/draft/:draftId" element={<DraftBoard />} />
    </Routes>
  );
}

export default App;
