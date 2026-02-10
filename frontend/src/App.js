import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import DraftSetup from "./pages/DraftSetup";
import DraftBoard from "./pages/DraftBoard";

function App() {
  return (
    <Routes>
      {/* Home route: draft setup */}
      <Route path="/" element={<DraftSetup />} />

      {/* Draft page route */}
      <Route path="/draft/:draftId" element={<DraftBoard />} />

      {/* Fallback: redirect unknown routes to home */}
      <Route path="*" element={<Navigate to="/" />} />
    </Routes>
  );
}

export default App;
