import React, { useEffect, useState } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";
import { tacticalVoice } from "../utils/tacticalVoice.js";

const REBOOT_LOGS = [
  ">> CRIMEMIND KERNEL 6.4 DIAGNOSTIC REBOOT INITIATED...",
  ">> INITIALIZING HARDWARE ENCLAVE & SECURE STORAGE... [OK]",
  ">> VERIFYING POSTGRESQL MULTI-POOL (10 CONNECTIONS)... [VERIFIED]",
  ">> COMPUTING CRYPTOGRAPHIC EVIDENCE MERKLE ROOT... [VALIDATED]",
  ">> INITIALIZING YOLOV11 SURVEILLANCE & BYTETRACK MATRIX... [ARMED]",
  ">> CBCA PSYCHOLOGICAL NLP & SVA ENGINE... [ACTIVE]",
  ">> CALIBRATING 3D THREE.JS BALLISTICS RAY-TRACER... [CALIBRATED]",
  ">> PURGING VOLATILE TELEMETRY CACHE... [CLEARED]",
  ">> RESTORING HOLOGRAPHIC NEURAL INTERFACE...",
  ">> ALL SYSTEMS NOMINAL. SYSTEM REBOOT COMPLETE.",
];

export function EmpRebootOverlay({ isActive, onComplete }) {
  const [displayedLogs, setDisplayedLogs] = useState([]);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    if (!isActive) {
      setDisplayedLogs([]);
      setProgress(0);
      return;
    }

    try {
      cyberAudio?.playSubBassPulse?.();
      cyberAudio?.playGlitch?.();
      tacticalVoice?.announceEmpReboot?.();
    } catch {}

    let logIdx = 0;
    const logInterval = setInterval(() => {
      if (logIdx < REBOOT_LOGS.length) {
        setDisplayedLogs((prev) => [...prev, REBOOT_LOGS[logIdx]]);
        logIdx++;
      } else {
        clearInterval(logInterval);
      }
    }, 240);

    const progInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 100) {
          clearInterval(progInterval);
          setTimeout(() => {
            try { cyberAudio?.playSuccess?.(); } catch {}
            onComplete();
          }, 350);
          return 100;
        }
        return prev + 8;
      });
    }, 180);

    return () => {
      clearInterval(logInterval);
      clearInterval(progInterval);
    };
  }, [isActive, onComplete]);

  if (!isActive) return null;

  return (
    <div className="cm-emp-reboot-overlay">
      <div className="cm-emp-crt-scanlines" />
      <div className="cm-emp-crt-flicker" />

      <div className="cm-emp-terminal-box font-mono">
        <div className="row justify-between items-center" style={{ borderBottom: "1px solid rgba(0, 255, 128, 0.3)", paddingBottom: 8, marginBottom: 12 }}>
          <div className="row items-center gap-2">
            <span className="cm-pulse-emerald" />
            <strong className="text-emerald">⚡ SYSTEM DIAGNOSTIC EMERGENCY REBOOT // LEVEL-5 PURGE</strong>
          </div>
          <span className="text-muted text-xs">KERNEL: 6.4.0-MIL-SPEC</span>
        </div>

        <div className="cm-emp-logs-feed">
          {displayedLogs.map((log, idx) => (
            <div key={idx} className="cm-emp-log-line">
              {log}
            </div>
          ))}
          <span className="cm-terminal-cursor">█</span>
        </div>

        <div style={{ marginTop: 18 }}>
          <div className="row justify-between text-xs" style={{ marginBottom: 6 }}>
            <span className="text-cyan">RE-INITIALIZATION PROGRESS:</span>
            <span className="text-emerald">{progress}%</span>
          </div>
          <div className="cm-cyber-progress-track">
            <div
              className="cm-cyber-progress-bar"
              style={{ width: `${progress}%`, background: "linear-gradient(90deg, #00E6A0, #00E5FF)" }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
