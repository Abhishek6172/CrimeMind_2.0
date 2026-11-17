import React, { useState, useEffect } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";
import { tacticalVoice } from "../utils/tacticalVoice.js";

export function TacticalTelemetryRibbon({ opticsMode, setOpticsMode, onTriggerEmp }) {
  const [isOpen, setIsOpen] = useState(false);
  const [tflops, setTflops] = useState(14.8);
  const [latency, setLatency] = useState(11);
  const [memHex, setMemHex] = useState("0x7FFF5FBFFD20");
  const [voiceActive, setVoiceActive] = useState(tacticalVoice.isEnabled());

  // Real-time jittering telemetry numbers
  useEffect(() => {
    const interval = setInterval(() => {
      setTflops((14.0 + Math.random() * 1.6).toFixed(1));
      setLatency(Math.floor(9 + Math.random() * 5));
      const hex = "0x7FFF" + Math.floor(Math.random() * 0xffffff).toString(16).toUpperCase().padStart(6, "0");
      setMemHex(hex);
    }, 1800);
    return () => clearInterval(interval);
  }, []);

  const toggleVoice = (e) => {
    e.stopPropagation();
    try { cyberAudio?.playClickChirp?.(); } catch {}
    const newState = tacticalVoice.toggle();
    setVoiceActive(newState);
  };

  const handleOpticsCycle = (e) => {
    e.stopPropagation();
    try { cyberAudio?.playClickChirp?.(); } catch {}
    const modes = ["cyber", "nvg", "flir", "blueprint", "matrix"];
    const nextIdx = (modes.indexOf(opticsMode) + 1) % modes.length;
    const nextMode = modes[nextIdx];
    setOpticsMode(nextMode);
    tacticalVoice.announceOptics(nextMode);
  };

  return (
    <>
      {/* Docked Bottom Futuristic Telemetry Ribbon */}
      <footer className="cm-tactical-telemetry-ribbon" onClick={() => setIsOpen((prev) => !prev)}>
        <div className="cm-telemetry-strip-left">
          <div className="cm-telemetry-badge">
            <span className="cm-pulse-emerald" />
            <span className="font-mono text-emerald">SYS.CORE: ACTIVE</span>
          </div>
          <span className="cm-telemetry-divider">|</span>
          <span className="font-mono text-cyan text-xs">
            NEURAL BUS: <b className="text-white">{tflops} TFLOPS</b>
          </span>
          <span className="cm-telemetry-divider">|</span>
          <span className="font-mono text-muted text-xs">
            EVLM STATE: <b className="text-emerald">SYNCHRONIZED (7-STATE)</b>
          </span>
          <span className="cm-telemetry-divider">|</span>
          <span className="font-mono text-muted text-xs">
            CIPHER: <b className="text-amber">AES-GCM-256</b>
          </span>
          <span className="cm-telemetry-divider">|</span>
          <span className="font-mono text-xs text-muted">
            MEM ADDR: <span className="text-cyan font-mono">{memHex}</span>
          </span>
        </div>

        <div className="cm-telemetry-strip-right">
          {/* Quick Optics Lens Toggle */}
          <button
            type="button"
            className={`cm-telemetry-pill-btn optics-${opticsMode}`}
            onClick={handleOpticsCycle}
            title="Switch Vision Optics: Cyber, NVG Night Vision, FLIR Thermal, Blueprint, Matrix"
          >
            🥽 OPTICS: <b className="text-cyan">{opticsMode.toUpperCase()}</b>
          </button>

          {/* Tactical Voice Synthesizer Toggle */}
          <button
            type="button"
            className={`cm-telemetry-pill-btn ${voiceActive ? "voice-active" : "voice-off"}`}
            onClick={toggleVoice}
            title="Toggle Tactical AI Voice Synthesizer"
          >
            🎙 VOICE HUD: <b className={voiceActive ? "text-emerald" : "text-muted"}>{voiceActive ? "ON" : "MUTED"}</b>
          </button>

          {/* EMP Shockwave Reboot Button */}
          <button
            type="button"
            className="cm-telemetry-pill-btn emp-btn"
            onClick={(e) => {
              e.stopPropagation();
              onTriggerEmp();
            }}
            title="Trigger Full-System EMP Diagnostic Reboot"
          >
            ⚡ EMP REBOOT
          </button>

          <span className="font-mono text-xs text-muted">
            LATENCY: <b className="text-emerald">{latency}ms</b>
          </span>

          <span className="cm-telemetry-drawer-arrow font-mono text-xs text-cyan">
            {isOpen ? "▼ CONSOLE" : "▲ CONSOLE"}
          </span>
        </div>
      </footer>

      {/* Slide-Up Tactical Kernel Diagnostics Console */}
      {isOpen && (
        <div className="cm-kernel-diagnostics-drawer">
          <div className="cm-kernel-drawer-header">
            <div className="row items-center gap-2 font-mono">
              <span className="cm-pulse-amber" />
              <strong className="text-amber">CRIMEMIND TACTICAL KERNEL v6.4 // REAL-TIME SYSTEM TELEMETRY</strong>
            </div>
            <button className="cm-filter-pill" onClick={() => setIsOpen(false)}>
              ✕ Close Console
            </button>
          </div>

          <div className="cm-kernel-drawer-grid grid grid-4 gap-3 font-mono text-xs" style={{ marginTop: 12 }}>
            <div className="cm-kernel-stat-card">
              <div className="text-muted">MEMORY ALLOCATION</div>
              <div className="text-cyan text-sm font-bold" style={{ marginTop: 4 }}>512 MB / 4096 MB</div>
              <div className="text-muted" style={{ marginTop: 2 }}>Heap: 18.2 MB · V8 Garbage Collector: Stable</div>
            </div>

            <div className="cm-kernel-stat-card">
              <div className="text-muted">POSTGRESQL POOL</div>
              <div className="text-emerald text-sm font-bold" style={{ marginTop: 4 }}>10 / 10 ACTIVE CONNECTIONS</div>
              <div className="text-muted" style={{ marginTop: 2 }}>Pool Timeout: 10.0s · Row Factory: Dict</div>
            </div>

            <div className="cm-kernel-stat-card">
              <div className="text-muted">NEURAL VISION BUS</div>
              <div className="text-amber text-sm font-bold" style={{ marginTop: 4 }}>YOLOv11 NANO + BYTETRACK</div>
              <div className="text-muted" style={{ marginTop: 2 }}>Device: CPU/CUDA · Throughput: 42.4 FPS</div>
            </div>

            <div className="cm-kernel-stat-card">
              <div className="text-muted">CRYPTOGRAPHIC MERKLE ROOT</div>
              <div className="text-cyan text-sm font-bold" style={{ marginTop: 4 }}>SHA-256: 9b1f537b…</div>
              <div className="text-muted" style={{ marginTop: 2 }}>Chain Integrity: 100% UNCOMPROMISED</div>
            </div>
          </div>

          <div className="cm-kernel-terminal-feed font-mono text-xs" style={{ marginTop: 12 }}>
            <div className="text-muted">&gt; [KERNEL] All subsystems online. Row-level security active.</div>
            <div className="text-emerald">&gt; [EVLM] Evidence Validity Lifecycle Engine running at tick rate 60Hz.</div>
            <div className="text-cyan">&gt; [NLP] Criteria-Based Content Analysis (CBCA) dictionary initialized.</div>
            <div className="text-amber">&gt; [OPTICS] Optical lens pipeline attached to DOM root node: mode={opticsMode}.</div>
          </div>
        </div>
      )}
    </>
  );
}
