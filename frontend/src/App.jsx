import React, { useState } from "react";
import ResearchLab from "./ResearchLab.jsx";
import CaseworkApp from "./CaseworkApp.jsx";
import { MouseEffects } from "./components/MouseEffects.jsx";
import "./styles.css";

export default function App() {
  const [mode, setMode] = useState("research");

  return (
    <div className="cm-universe">
      {/* Global Interactive Cursor Spotlight, Trailing Halo, and Canvas Particle Grid */}
      <MouseEffects />

      {/* Primary Application Shell */}
      {mode === "casework" ? (
        <CaseworkApp onOpenResearch={() => setMode("research")} />
      ) : (
        <div className="cm-mode-wrap">
          <ResearchLab onOpenCasework={() => setMode("casework")} />
        </div>
      )}
    </div>
  );
}
