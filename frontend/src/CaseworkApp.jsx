import React, { useEffect, useState } from "react";
import { api, hasToken, setToken, setUnauthorizedHandler } from "./api.js";
import { useLoad } from "./hooks.js";
import { Async, Badge, Card, StatBox, time } from "./components/ui.jsx";
import CaseView from "./pages/CaseView.jsx";
import { BiometricScanner } from "./components/BiometricScanner.jsx";
import { AudioWaveform } from "./components/AudioWaveform.jsx";
import { CommandPalette } from "./components/CommandPalette.jsx";
import { TacticalCompass } from "./components/TacticalCompass.jsx";
import { ScrambleText } from "./components/ScrambleText.jsx";
import { HoloGlobe } from "./components/HoloGlobe.jsx";
import { TacticalTelemetryRibbon } from "./components/TacticalTelemetryRibbon.jsx";
import { EmpRebootOverlay } from "./components/EmpRebootOverlay.jsx";
import { cyberAudio } from "./utils/cyberAudio.js";
import { tacticalVoice } from "./utils/tacticalVoice.js";

function Login({ onLogin, onOpenResearch }) {
  const [u, setU] = useState("admin"),
    [p, setP] = useState("crimemind-demo"),
    [err, setErr] = useState(""),
    [busy, setBusy] = useState(false);

  const executeLogin = async (username, password) => {
    setBusy(true);
    setErr("");
    try {
      const r = await api("/auth/login", {
        method: "POST",
        body: { username: username || u, password: password || p },
      });
      setToken(r.access_token);
      cyberAudio.playSubBassPulse();
      onLogin(r.user);
    } catch (x) {
      cyberAudio.playGlitchAlert();
      if (x.status === 405 || x.status === 404 || x.status === 0) {
        setErr("Live Casework backend is not running on this domain. Click the button below to explore the Research Lab & Training Case.");
      } else {
        setErr(x.message || "Authentication rejected (401)");
      }
    } finally {
      setBusy(false);
    }
  };

  const submit = (e) => {
    e.preventDefault();
    executeLogin(u, p);
  };

  const setPreset = (username) => {
    setU(username);
    setP("crimemind-demo");
    cyberAudio.playClickChirp();
  };

  return (
    <main className="login cm-login-universe">
      <div className="cm-login-frame">
        <div className="cm-login-header">
          <div className="cm-logo-mark">
            <span className="cm-logo-diamond">◈</span>
          </div>
          <h1>
            <ScrambleText text="CRIMEMIND" speed={30} />
          </h1>
          <p className="cm-login-sub font-mono">
            COMMAND CENTRE // INVESTIGATIVE OPERATING SYSTEM
          </p>
          <div className="cm-login-pill">
            <span className="cm-pulse-emerald" />
            <span>SYNTHETIC INTEGRITY PROTOCOL ACTIVE</span>
          </div>
        </div>

        {/* Biometric Rapid Handprint Decryption Scanner */}
        <BiometricScanner
          label="CAPACITIVE RETINA / BIOMETRIC AUTH"
          onVerified={() => executeLogin(u || "admin", p || "crimemind-demo")}
        />

        <div className="cm-or-divider font-mono text-muted small">
          <span>— OR MANUAL SECURITY CIPHER —</span>
        </div>

        <form onSubmit={submit} className="card cm-login-card">
          <div className="cm-form-group">
            <label className="font-mono small">
              OPERATOR ID / USERNAME
              <input
                value={u}
                onChange={(e) => setU(e.target.value)}
                autoComplete="username"
                placeholder="e.g. admin or inv.asha"
                autoFocus
                className="cm-cyber-input"
              />
            </label>
          </div>

          <div className="cm-form-group">
            <label className="font-mono small">
              ACCESS CIPHER / PASSWORD
              <input
                type="password"
                value={p}
                onChange={(e) => setP(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••••••"
                className="cm-cyber-input"
              />
            </label>
          </div>

          {err && (
            <div className="state error cm-cyber-error cm-chromatic-glitch" role="alert">
              <span>⚠️</span>
              <span>{err}</span>
            </div>
          )}

          <button
            className="primary cm-login-submit"
            disabled={busy || !u || !p}
          >
            {busy ? (
              <span className="row items-center gap-2">
                <span className="cm-radar-spinner small" />
                <span>AUTHENTICATING ACCESS CREDENTIALS…</span>
              </span>
            ) : (
              "INITIALIZE COMMAND SESSION ↗"
            )}
          </button>

          {/* Quick preset credentials bar */}
          <div className="cm-quick-presets">
            <span className="small text-muted font-mono">QUICK OPERATOR SELECT:</span>
            <div className="row gap-2" style={{ marginTop: 4 }}>
              <button
                type="button"
                className="cm-preset-btn"
                onClick={() => setPreset("admin")}
              >
                admin
              </button>
              <button
                type="button"
                className="cm-preset-btn"
                onClick={() => setPreset("inv.asha")}
              >
                inv.asha
              </button>
              <button
                type="button"
                className="cm-preset-btn"
                onClick={() => setPreset("sup.rao")}
              >
                sup.rao
              </button>
            </div>
            <small className="muted font-mono" style={{ display: "block", marginTop: 8 }}>
              Default password: <code>crimemind-demo</code>
            </small>
          </div>
        </form>
      </div>
    </main>
  );
}

function NewCase({ onCreated }) {
  const [title, setTitle] = useState(""),
    [err, setErr] = useState(null),
    [busy, setBusy] = useState(false);

  const go = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await api("/cases", { method: "POST", body: { title } });
      setTitle("");
      cyberAudio.playAccessGranted();
      onCreated(r.case_ref);
    } catch (x) {
      cyberAudio.playGlitchAlert();
      setErr(x);
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="row cm-new-case-form" onSubmit={go}>
      <input
        placeholder="Enter new case title…"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        aria-label="New case title"
        className="cm-cyber-input"
        style={{ minWidth: 260 }}
      />
      <button
        className="primary small"
        disabled={busy || title.trim().length < 3}
      >
        {busy ? "Opening…" : "＋ Initialize Case"}
      </button>
      {err && <span className="fielderr font-mono small">{err.message}</span>}
    </form>
  );
}

function CaseList({ onOpen, user }) {
  const st = useLoad(() => api("/cases"), []);
  const canCreate = ["SUPERVISOR", "ADMINISTRATOR"].includes(user.role);
  const [search, setSearch] = useState("");

  const handleOpen = (caseRef) => {
    try { cyberAudio?.playClickChirp?.(); } catch {}
    try { tacticalVoice?.announceCaseLoaded?.(caseRef); } catch {}
    onOpen(caseRef);
  };

  return (
    <div className="cm-caselist-workspace">
      <div className="cm-caselist-hero">
        <div>
          <span className="font-mono text-amber text-xs letter-spacing-wide">
            INVESTIGATIVE DOSSIER REGISTRY
          </span>
          <h1>
            <ScrambleText text="Active Forensic Cases" speed={25} />
          </h1>
          <p className="text-muted">
            Authorized case dockets and evidence vaults under your jurisdiction.
          </p>
        </div>
        <HoloGlobe width={120} height={120} interactive={true} />
        {canCreate && <NewCase onCreated={onOpen} />}
      </div>

      <div className="cm-caselist-filterbar">
        <input
          type="text"
          placeholder="Filter cases by title, reference ID, or status…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="cm-cyber-input"
          style={{ maxWidth: 420 }}
        />
        <div className="grow" />
        <span className="font-mono small text-cyan">
          AUTHORIZATION: {user.role}
        </span>
      </div>

      <Async
        state={st}
        empty={Object.assign((d) => !d?.cases?.length, {
          message: "You have not been assigned to any case docket.",
        })}
      >
        {(d) => {
          const casesList = (d && d.cases) || [];
          const filtered = casesList.filter(
            (c) =>
              c.title?.toLowerCase().includes(search.toLowerCase()) ||
              c.case_ref?.toLowerCase().includes(search.toLowerCase()) ||
              c.status?.toLowerCase().includes(search.toLowerCase())
          );

          if (!filtered.length) {
            return (
              <div className="state cm-empty-state">
                No cases matched search query "{search}".
              </div>
            );
          }

          return (
            <div className="cm-case-grid">
              {filtered.map((c) => (
                <div
                  key={c.case_ref}
                  className="cm-case-card"
                  onClick={() => handleOpen(c.case_ref)}
                >
                  <div className="cm-case-card-glow" />
                  <div className="cm-case-card-header">
                    <span className="font-mono text-cyan text-sm">
                      {c.case_ref}
                    </span>
                    <Badge kind={c.status} />
                  </div>
                  <h3>{c.title}</h3>
                  <div className="cm-case-card-meta">
                    <span className="font-mono small text-muted">
                      Created: {time(c.created_at)}
                    </span>
                  </div>
                  <div className="cm-case-card-footer">
                    <span className="cm-open-case-btn">Open Investigation ↗</span>
                  </div>
                </div>
              ))}
            </div>
          );
        }}
      </Async>
    </div>
  );
}

class Boundary extends React.Component {
  state = { err: null };
  static getDerivedStateFromError(err) {
    return { err };
  }
  render() {
    if (!this.state.err) return this.props.children;
    return (
      <div className="state error cm-cyber-error cm-chromatic-glitch" role="alert" style={{ margin: 24 }}>
        <strong>PANEL DISPLAY EXCEPTION</strong>
        <div className="small font-mono">
          {String(this.state.err.message || this.state.err)}
        </div>
        <button onClick={() => this.setState({ err: null })} style={{ marginTop: 10 }}>
          ↻ Retry Component
        </button>
      </div>
    );
  }
}

export default function CaseworkApp({ onOpenResearch }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(!hasToken());
  const [caseRef, setCaseRef] = useState(null);
  const [now, setNow] = useState(new Date());

  // Tactical Vision Modes: "cyber" | "nvg" | "flir" | "blueprint"
  const [opticsMode, setOpticsMode] = useState("cyber");
  const [isAudioMuted, setIsAudioMuted] = useState(cyberAudio.isMuted());
  const [isPaletteOpen, setIsPaletteOpen] = useState(false);
  const [isEmpActive, setIsEmpActive] = useState(false);

  const logout = () => {
    setToken(null);
    setUser(null);
    setCaseRef(null);
  };

  useEffect(() => {
    setUnauthorizedHandler(logout);
    if (hasToken()) {
      api("/auth/me")
        .then(setUser, () => setToken(null))
        .finally(() => setReady(true));
    }
  }, []);

  // Live system clock ticker
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Global Ctrl+K / Cmd+K listener
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsPaletteOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Cycle optics modes
  const cycleOptics = (forcedMode) => {
    const modes = ["cyber", "nvg", "flir", "blueprint", "matrix"];
    const next = forcedMode || modes[(modes.indexOf(opticsMode) + 1) % modes.length];
    setOpticsMode(next);
    document.documentElement.setAttribute("data-optics", next);
    try {
      cyberAudio?.playClickChirp?.();
      tacticalVoice?.announceOptics?.(next);
    } catch {}
  };

  const toggleSound = () => {
    const muted = cyberAudio.toggleMute();
    setIsAudioMuted(muted);
    if (!muted) cyberAudio?.playClickChirp?.();
  };

  // Trigger full-interface EMP Diagnostic Reboot
  const [isEmpRebooting, setIsEmpRebooting] = useState(false);
  const triggerEmpShockwave = () => {
    setIsEmpRebooting(true);
  };

  // Handle actions executed from Command Palette
  const handlePaletteAction = (type, value) => {
    if (type === "optics") {
      cycleOptics(value);
    } else if (type === "audio") {
      toggleSound();
    } else if (type === "emp") {
      triggerEmpShockwave();
    } else if (type === "research" && onOpenResearch) {
      onOpenResearch();
    } else if (type === "tab") {
      // Dispatched tab selection
      const tabBtn = document.querySelector(`.cm-cyber-tab[aria-label*="${value}"]`) ||
        Array.from(document.querySelectorAll(".cm-cyber-tab")).find((b) => b.textContent.includes(value));
      if (tabBtn) tabBtn.click();
    }
  };

  if (!ready) {
    return (
      <div className="state cm-loading-state full-screen">
        <div className="cm-radar-spinner" />
        <span>INITIALIZING CRIMEMIND COMMAND SHELL…</span>
      </div>
    );
  }

  if (!user) return <Login onLogin={setUser} onOpenResearch={onOpenResearch} />;

  const timeStr = now.toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour12: false,
  });

  return (
    <div
      className={`cm-command-shell ${isEmpActive ? "cm-emp-shockwave-active" : ""}`}
      data-optics={opticsMode}
    >
      {/* Full-Interface EMP Diagnostic CRT Reboot Overlay */}
      <EmpRebootOverlay
        isActive={isEmpRebooting}
        onComplete={() => setIsEmpRebooting(false)}
      />

      {/* Global Command Palette HUD Overlay */}
      <CommandPalette
        isOpen={isPaletteOpen}
        onClose={() => setIsPaletteOpen(false)}
        onSelectAction={handlePaletteAction}
        caseRef={caseRef}
      />

      {/* Top Cybernetic Command Header */}
      <header className="top cm-command-header">
        <div className="cm-brand-cluster">
          <button className="brand cm-brand-glow" onClick={() => setCaseRef(null)}>
            CRIMEMIND
          </button>
          <span className="cm-version-badge font-mono">OS v6.4</span>
        </div>

        <div className="cm-header-telemetry font-mono small">
          <span className="cm-telemetry-item">
            <span className="cm-pulse-emerald" />
            <span className="text-emerald">ONLINE</span>
          </span>
          <span className="cm-telemetry-sep">|</span>
          <span className="cm-telemetry-item">
            CLOCK: <span className="text-cyan">{timeStr} IST</span>
          </span>
          <span className="cm-telemetry-sep">|</span>
          <span className="cm-telemetry-item">
            DB: <span className="text-amber">cm_app @ PG16</span>
          </span>
        </div>

        {/* Live Spatial Azimuth Compass */}
        <TacticalCompass />

        {/* Live Audio Spectrum Comms Waveform */}
        <AudioWaveform width={100} height={22} bars={16} />

        <div className="grow" />

        {/* Global Command Palette Trigger Pill */}
        <button
          type="button"
          className="cm-palette-trigger-btn"
          onClick={() => setIsPaletteOpen(true)}
          title="Open Global Command Palette (Ctrl + K)"
        >
          <span className="cm-palette-kbd">⌘K</span>
          <span>COMMAND</span>
        </button>

        {/* Interactive EMP Threat Matrix Diagnostic */}
        <button
          type="button"
          className="cm-emp-threat-btn"
          onClick={triggerEmpShockwave}
          title="Trigger Electromagnetic Pulse (EMP) Integrity Diagnostic"
        >
          <span>⚡</span>
          <span className="font-mono text-xs">EMP DIAG</span>
        </button>

        {/* Tactical Optics Mode Switcher */}
        <button
          type="button"
          className={`cm-optics-btn mode-${opticsMode}`}
          onClick={() => cycleOptics()}
          title="Toggle Tactical Vision Optics (Cyber / NVG Night Vision / FLIR Thermal / Blueprint)"
        >
          <span>🥽</span>
          <span className="font-mono text-xs">OPTICS: {opticsMode.toUpperCase()}</span>
        </button>

        {/* Procedural Audio Mute Toggle */}
        <button
          type="button"
          className={`cm-audio-toggle-btn ${isAudioMuted ? "muted" : "active"}`}
          onClick={toggleSound}
          title={isAudioMuted ? "Unmute Tactical SFX" : "Mute Tactical SFX"}
        >
          <span>{isAudioMuted ? "🔇 SFX OFF" : "🔊 SFX ON"}</span>
        </button>

        {/* Mode Switcher to Research Lab */}
        {onOpenResearch && (
          <button
            type="button"
            className="cm-nav-mode-btn"
            onClick={onOpenResearch}
            title="Switch to Scientific Research Lab"
          >
            <span>🔬</span> Research Lab
          </button>
        )}

        <div className="cm-user-badge-cluster">
          <div className="cm-user-info">
            <span className="cm-username font-mono">{user.username}</span>
            <Badge kind={user.role} />
          </div>
          <button className="cm-signout-btn" onClick={logout} title="Sign Out">
            Sign out
          </button>
        </div>
      </header>

      {/* Main Content Pane */}
      <main className="page cm-command-main" style={{ paddingBottom: 48 }}>
        {caseRef ? (
          <Boundary key={caseRef}>
            <CaseView
              key={caseRef}
              caseRef={caseRef}
              user={user}
              onBack={() => setCaseRef(null)}
            />
          </Boundary>
        ) : (
          <Boundary>
            <CaseList onOpen={setCaseRef} user={user} />
          </Boundary>
        )}
      </main>

      {/* Docked Bottom Futuristic Telemetry Ribbon & Diagnostics Console */}
      <TacticalTelemetryRibbon
        opticsMode={opticsMode}
        setOpticsMode={cycleOptics}
        onTriggerEmp={triggerEmpShockwave}
      />
    </div>
  );
}
