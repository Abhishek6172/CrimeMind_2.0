import React, { useEffect, useState } from "react";

export function TacticalCompass() {
  const [azimuth, setAzimuth] = useState(142);

  useEffect(() => {
    const handleMove = (e) => {
      const angle = Math.round((e.clientX / window.innerWidth) * 360);
      setAzimuth(angle);
    };
    window.addEventListener("pointermove", handleMove, { passive: true });
    return () => window.removeEventListener("pointermove", handleMove);
  }, []);

  return (
    <div className="cm-tactical-compass" title="Tactical Heading & Spatial Azimuth">
      <div className="cm-compass-dial" style={{ transform: `rotate(${-azimuth}deg)` }}>
        <span className="cm-compass-n">N</span>
        <span className="cm-compass-e">E</span>
        <span className="cm-compass-s">S</span>
        <span className="cm-compass-w">W</span>
      </div>
      <div className="cm-compass-needle" />
      <div className="cm-compass-readout font-mono text-cyan">
        <span>{String(azimuth).padStart(3, "0")}°</span>
      </div>
    </div>
  );
}
