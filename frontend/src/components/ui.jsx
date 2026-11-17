import React from "react";
import { TiltCard } from "./TiltCard.jsx";

export const Badge = ({ kind, children }) => {
  const norm = String(kind ?? "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return (
    <span className={`badge b-${norm}`}>
      <span className="badge-glow" />
      {children ?? kind}
    </span>
  );
};

export function Async({ state, empty, children }) {
  if (state.loading) {
    return (
      <div className="state cm-loading-state">
        <div className="cm-radar-spinner" />
        <span>PROCESSING TELEMETRY STREAM…</span>
      </div>
    );
  }
  if (state.error) {
    return (
      <div className="state error cm-cyber-error" role="alert">
        <div className="cm-error-header">
          <span className="cm-blink">⚠️</span>
          <strong>TELEMETRY FETCH EXCEPTION</strong>
        </div>
        <p className="cm-error-msg">{state.error.message}</p>
        {state.error.requestId && (
          <div className="muted small font-mono">REQ_ID: {state.error.requestId}</div>
        )}
        <div style={{ marginTop: 10 }}>
          <button className="primary" onClick={state.reload}>↻ Retry Request</button>
        </div>
      </div>
    );
  }
  if (empty && empty(state.data)) {
    return (
      <div className="state cm-empty-state">
        <span className="cm-empty-glyph">⌖</span>
        <span>{empty.message || "No telemetry records discovered for current filter criteria."}</span>
      </div>
    );
  }
  return children(state.data);
}

// Card is now an interactive 3D TiltCard by default
export const Card = TiltCard;

export const Notice = ({ children, level = "info" }) => (
  <div className={`notice cm-notice level-${level}`}>
    <span className="cm-notice-beam" />
    <span className="cm-notice-icon">ℹ</span>
    <div className="cm-notice-body">{children}</div>
  </div>
);

export function Table({ rows, cols, onRow, empty = "No records located." }) {
  if (!rows?.length) return <div className="state cm-empty-state">{empty}</div>;
  return (
    <div className="tablewrap cm-cyber-tablewrap">
      <table className="cm-cyber-table">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c.key || c.label}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr
              key={i}
              onClick={onRow ? () => onRow(r) : undefined}
              className={onRow ? "click" : ""}
            >
              {cols.map((c) => (
                <td key={c.key || c.label}>
                  {c.render ? c.render(r) : fmt(r[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StatBox({ label, value, sub, icon, trend, accent = "cyan" }) {
  return (
    <div className={`cm-stat-box accent-${accent}`}>
      <div className="cm-stat-header">
        <span className="cm-stat-label">{label}</span>
        {icon && <span className="cm-stat-icon">{icon}</span>}
      </div>
      <div className="cm-stat-value">{value}</div>
      {(sub || trend) && (
        <div className="cm-stat-footer">
          {trend && <span className="cm-stat-trend">{trend}</span>}
          {sub && <span className="cm-stat-sub">{sub}</span>}
        </div>
      )}
      <div className="cm-stat-corner" />
    </div>
  );
}

export function CyberProgress({ value = 0, max = 100, label, color = "cyan" }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={`cm-progress-wrap color-${color}`}>
      {label && (
        <div className="cm-progress-meta">
          <span>{label}</span>
          <b>{pct.toFixed(1)}%</b>
        </div>
      )}
      <div className="cm-progress-track">
        <div className="cm-progress-bar" style={{ width: `${pct}%` }}>
          <span className="cm-progress-scanner" />
        </div>
      </div>
    </div>
  );
}

export function fmt(v) {
  if (v == null) return <span className="muted">—</span>;
  if (Array.isArray(v)) return v.join(", ") || <span className="muted">—</span>;
  if (typeof v === "object") return <code className="json-inline">{JSON.stringify(v)}</code>;
  if (typeof v === "string" && /^\d{4}-\d\d-\d\dT/.test(v)) return time(v);
  return String(v);
}

export const time = (v) =>
  v
    ? new Date(v).toLocaleString("en-IN", {
        timeZone: "Asia/Kolkata",
        dateStyle: "medium",
        timeStyle: "short",
      }) + " IST"
    : "—";
