import React, { useState, useRef, useEffect } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";

export function BiometricScanner({ onVerified, label = "BIOMETRIC CIPHER SCANNER" }) {
  const [progress, setProgress] = useState(0);
  const [isScanning, setIsScanning] = useState(false);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const intervalRef = useRef(null);

  const startScan = (e) => {
    e.preventDefault();
    if (isUnlocked) return;
    setIsScanning(true);
    cyberAudio.playScanTone();

    intervalRef.current = setInterval(() => {
      setProgress((p) => {
        if (p >= 100) {
          clearInterval(intervalRef.current);
          setIsScanning(false);
          setIsUnlocked(true);
          cyberAudio.playAccessGranted();
          if (onVerified) onVerified();
          return 100;
        }
        if (p % 25 === 0) {
          cyberAudio.playScanTone();
        }
        return p + 4;
      });
    }, 45);
  };

  const cancelScan = () => {
    if (isUnlocked) return;
    clearInterval(intervalRef.current);
    setIsScanning(false);
    setProgress(0);
  };

  useEffect(() => {
    return () => clearInterval(intervalRef.current);
  }, []);

  return (
    <div className="cm-biometric-container">
      <div className="cm-bio-header">
        <span className="font-mono text-cyan text-xs">⌖ {label}</span>
        <span className="font-mono text-muted text-xs">
          {isUnlocked ? "LEVEL 4 GRANTED" : isScanning ? `DECRYPTING: ${progress}%` : "PRESS & HOLD PAD"}
        </span>
      </div>

      <div
        className={`cm-biometric-pad ${isScanning ? "scanning" : ""} ${isUnlocked ? "unlocked" : ""}`}
        onPointerDown={startScan}
        onPointerUp={cancelScan}
        onPointerLeave={cancelScan}
        role="button"
        tabIndex={0}
        aria-label="Hold to scan biometric credentials"
      >
        {/* Holographic Ring Reticles */}
        <div className="cm-bio-ring ring-outer" />
        <div className="cm-bio-ring ring-middle" />
        <div className="cm-bio-ring ring-inner" />

        {/* Laser Scanning Beam */}
        <div className="cm-bio-laser" />

        {/* SVG Fingerprint / Retina Hologram */}
        <svg viewBox="0 0 100 100" className="cm-bio-fingerprint" aria-hidden="true">
          <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="1.2" strokeDasharray="6 4" />
          <path d="M 50 20 A 30 30 0 0 1 78 45" fill="none" stroke="currentColor" strokeWidth="2.5" />
          <path d="M 22 45 A 30 30 0 0 1 50 20" fill="none" stroke="currentColor" strokeWidth="2.5" />
          <path d="M 50 30 A 20 20 0 0 1 68 50" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M 32 50 A 20 20 0 0 1 50 30" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M 50 40 A 10 10 0 0 1 58 55" fill="none" stroke="currentColor" strokeWidth="2" />
          <path d="M 42 55 A 10 10 0 0 1 50 40" fill="none" stroke="currentColor" strokeWidth="2" />
          <circle cx="50" cy="50" r="4" fill="currentColor" />
        </svg>

        {/* Dynamic Progress Ring */}
        <svg className="cm-bio-svg-progress" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="54" className="cm-bio-track" />
          <circle
            cx="60"
            cy="60"
            r="54"
            className="cm-bio-fill"
            style={{
              strokeDasharray: 339.29,
              strokeDashoffset: 339.29 - (339.29 * progress) / 100,
            }}
          />
        </svg>

        <div className="cm-bio-status-text font-mono">
          {isUnlocked ? "AUTHENTICATED" : isScanning ? `${progress}%` : "HOLD SENSOR"}
        </div>
      </div>
    </div>
  );
}
