import React, { useEffect, useRef } from "react";

export function AudioWaveform({ width = 110, height = 24, bars = 18, active = true }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let animId = null;
    let phase = 0;

    const render = () => {
      ctx.clearRect(0, 0, width, height);
      phase += 0.08;

      const barWidth = Math.max(2, Math.floor(width / bars) - 2);

      for (let i = 0; i < bars; i++) {
        // Multi-frequency harmonic wave simulation
        const factor = Math.sin(phase + i * 0.45) * 0.4 + Math.cos(phase * 1.6 + i * 0.25) * 0.35 + 0.5;
        const barHeight = Math.max(3, Math.min(height - 2, factor * height * 0.85));

        const x = i * (barWidth + 2);
        const y = (height - barHeight) / 2;

        const grad = ctx.createLinearGradient(0, y, 0, y + barHeight);
        grad.addColorStop(0, "#00E5FF");
        grad.addColorStop(1, "#FFB52E");

        ctx.fillStyle = grad;
        ctx.fillRect(x, y, barWidth, barHeight);
      }

      animId = requestAnimationFrame(render);
    };

    if (active) {
      animId = requestAnimationFrame(render);
    } else {
      ctx.clearRect(0, 0, width, height);
    }

    return () => {
      if (animId) cancelAnimationFrame(animId);
    };
  }, [width, height, bars, active]);

  return (
    <div className="cm-waveform-pill" title="Live Surveillance Comms Telemetry">
      <span className="cm-waveform-tag font-mono">COMMS:</span>
      <canvas ref={canvasRef} width={width} height={height} className="cm-waveform-canvas" />
    </div>
  );
}
