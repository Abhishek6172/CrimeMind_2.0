import React, { useState, useEffect } from "react";
import { api } from "../api.js";
import { Card, Badge, StatBox } from "../components/ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";

export default function FinancialForensicsView({ caseRef }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [threshold, setThreshold] = useState(50000.0);
  const [selectedTx, setSelectedTx] = useState(null);
  const [isAuditing, setIsAuditing] = useState(false);

  const runAudit = async () => {
    setIsAuditing(true);
    cyberAudio.playScan?.();
    try {
      const res = await api("/ml/financial/audit", {
        method: "POST",
        body: {
          case_id: caseRef,
          reporting_threshold: threshold,
        },
      });
      setData(res);
      if (res.transactions?.length) {
        setSelectedTx(res.transactions.find((t) => t.is_anomaly) || res.transactions[0]);
      }
    } catch (err) {
      console.error("Financial audit failed", err);
    } finally {
      setLoading(false);
      setIsAuditing(false);
    }
  };

  useEffect(() => {
    runAudit();
  }, [caseRef, threshold]);

  if (loading) {
    return (
      <div className="p-8 text-center font-mono text-cyan">
        <span className="cm-pulse-dot" /> EXECUTING SCIKIT-LEARN ISOLATION FOREST & BENFORD ANOMALY AUDIT...
      </div>
    );
  }

  const benford = data?.benford_law_conformity;

  return (
    <div className="space-y-6">
      {/* Top Banner Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border-subtle pb-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xl">💳</span>
            <h1 className="text-2xl font-bold tracking-wider text-white uppercase">
              Financial Forensics & Smurfing Detector
            </h1>
            <Badge tone="gold">Isolation Forest ML</Badge>
          </div>
          <p className="text-xs text-muted font-mono mt-1">
            Outlier Isolation Trees (100 Estimators) + Structuring Analytics + Benford's Law Forensic Accounting
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-mono text-xs">
            <span className="text-muted">REPORTING CAP:</span>
            <select
              value={threshold}
              onChange={(e) => setThreshold(parseFloat(e.target.value))}
              className="bg-slate-900 border border-gold/40 text-gold rounded px-2 py-1 text-xs"
            >
              <option value="50000">₹50,000 (India PAN Cap)</option>
              <option value="10000">$10,000 (US BSA / FinCEN Cap)</option>
              <option value="100000">₹1,00,000 (High-Value Cap)</option>
            </select>
          </div>

          <button
            className="btn btn-outline border-gold text-gold hover:bg-gold hover:text-black font-mono text-xs px-3 py-1.5"
            onClick={runAudit}
            disabled={isAuditing}
          >
            {isAuditing ? "🔄 AUDITING..." : "⚡ RE-RUN ISOLATION FOREST"}
          </button>
        </div>
      </div>

      {/* 4 Stat KPI Metric Boxes */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatBox
          label="TRANSACTIONS AUDITED"
          value={data?.total_transactions_analyzed || 0}
          caption="Ledger Records"
          accent="cyan"
        />
        <StatBox
          label="ANOMALIES FLAGGED"
          value={data?.anomalies_detected || 0}
          caption="Outlier Isolation"
          accent="magenta"
        />
        <StatBox
          label="SMURFING TXS"
          value={data?.smurfing_transactions_count || 0}
          caption="Structured Deposits"
          accent="gold"
        />
        <StatBox
          label="SUSPICIOUS VOLUME"
          value={`₹${(data?.total_suspicious_volume || 0).toLocaleString()}`}
          caption="Laundered Estimate"
          accent="emerald"
        />
      </div>

      {/* Main Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Transaction Ledger & Benford Distribution */}
        <div className="lg:col-span-2 space-y-4">
          {/* Benford's Law Visualization */}
          <Card className="p-4 border border-cyan/30 bg-slate-900/60">
            <div className="flex items-center justify-between mb-3 font-mono text-xs">
              <span className="text-cyan font-bold">
                BENFORD'S LAW FIRST-DIGIT DISTRIBUTION (FORENSIC ACCOUNTING)
              </span>
              <span
                className={`font-bold px-2 py-0.5 rounded text-[10px] ${
                  benford?.violates_benford_law
                    ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                    : "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                }`}
              >
                {benford?.violates_benford_law ? "VIOLATION DETECTED [!]" : "NATURAL CONFORMITY"}
              </span>
            </div>

            {/* Digits 1 to 9 Bars */}
            <div className="grid grid-cols-9 gap-2 pt-2 pb-1 text-center font-mono">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((digit) => {
                const obs = benford?.digit_distribution?.[String(digit)]?.observed || 0;
                const exp = benford?.digit_distribution?.[String(digit)]?.expected || 0;
                const isAbnormal = Math.abs(obs - exp) > 0.15;

                return (
                  <div key={digit} className="space-y-1">
                    <div className="h-28 flex items-end justify-center gap-1 bg-slate-950/60 rounded p-1 border border-slate-800">
                      {/* Observed Bar */}
                      <div
                        className={`w-2.5 rounded-t transition-all ${
                          isAbnormal ? "bg-rose-500" : "bg-cyan"
                        }`}
                        style={{ height: `${Math.min(100, obs * 250)}%` }}
                        title={`Digit ${digit} Observed: ${(obs * 100).toFixed(1)}%`}
                      />
                      {/* Expected Bar */}
                      <div
                        className="w-2.5 rounded-t bg-slate-600/60"
                        style={{ height: `${Math.min(100, exp * 250)}%` }}
                        title={`Digit ${digit} Expected: ${(exp * 100).toFixed(1)}%`}
                      />
                    </div>
                    <span className="text-xs font-bold text-white block">{digit}</span>
                    <span className="text-[9px] text-muted block">{(obs * 100).toFixed(0)}%</span>
                  </div>
                );
              })}
            </div>

            <p className="mt-2 text-xs text-muted font-mono">
              Interpretation: {benford?.interpretation} (Mean Absolute Deviation: {benford?.mean_absolute_deviation})
            </p>
          </Card>

          {/* Transaction Ledger Table */}
          <Card className="p-4 border border-border-subtle bg-slate-900/40">
            <h3 className="text-sm font-bold tracking-wide text-white uppercase mb-3 flex items-center gap-2">
              <span>📋</span> Transaction Audit Ledger (Isolation Forest Output)
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-mono text-xs">
                <thead>
                  <tr className="border-b border-border-subtle text-muted text-[10px] uppercase">
                    <th className="p-2">TX ID</th>
                    <th className="p-2">Sender ➔ Recipient</th>
                    <th className="p-2 text-right">Amount</th>
                    <th className="p-2 text-center">Anomaly Score</th>
                    <th className="p-2">Classification</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {data?.transactions?.map((tx) => {
                    const isSelected = selectedTx?.id === tx.id;
                    return (
                      <tr
                        key={tx.id}
                        className={`cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-cyan/10 border-l-2 border-cyan"
                            : "hover:bg-slate-800/40"
                        }`}
                        onClick={() => {
                          setSelectedTx(tx);
                          cyberAudio.playClick?.();
                        }}
                      >
                        <td className="p-2 font-bold text-cyan">{tx.id}</td>
                        <td className="p-2">
                          <span className="text-white">{tx.sender}</span>
                          <span className="text-muted mx-1.5">➔</span>
                          <span className="text-gold">{tx.recipient}</span>
                        </td>
                        <td className="p-2 text-right font-bold text-white">
                          ₹{tx.amount.toLocaleString()}
                        </td>
                        <td className="p-2 text-center">
                          <span
                            className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                              tx.anomaly_score > 0.65
                                ? "bg-rose-500/20 text-rose-300"
                                : "bg-cyan/10 text-cyan"
                            }`}
                          >
                            {(tx.anomaly_score * 100).toFixed(0)}%
                          </span>
                        </td>
                        <td className="p-2">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              tx.status.includes("HIGH")
                                ? "bg-rose-500/20 text-rose-400 border border-rose-500/40"
                                : tx.status.includes("ELEVATED")
                                ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                                : "bg-emerald-500/20 text-emerald-400"
                            }`}
                          >
                            {tx.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        {/* Right Col: Transaction Forensic Detail & Shell Fanout */}
        <div className="space-y-4">
          {/* Selected TX Detail Card */}
          {selectedTx && (
            <Card className="p-5 border-2 border-gold/40 bg-slate-900/80 shadow-lg">
              <span className="text-xs font-mono text-gold font-bold">FORENSIC TRANSACTION INSPECTOR</span>
              <h2 className="text-xl font-bold text-white mt-1">₹{selectedTx.amount.toLocaleString()}</h2>
              <div className="text-xs font-mono text-muted mb-3">ID: {selectedTx.id} | Channel: {selectedTx.channel}</div>

              <div className="space-y-2 text-xs font-mono border-t border-slate-800 pt-3">
                <div>
                  <span className="text-muted block text-[10px]">SENDER:</span>
                  <span className="text-white font-bold">{selectedTx.sender}</span>
                </div>
                <div>
                  <span className="text-muted block text-[10px]">RECIPIENT:</span>
                  <span className="text-gold font-bold">{selectedTx.recipient}</span>
                </div>
                <div className="flex justify-between border-t border-slate-800 pt-2">
                  <span className="text-muted">Isolation Forest Outlier Score:</span>
                  <span className="text-rose-400 font-bold">{(selectedTx.anomaly_score * 100).toFixed(1)}%</span>
                </div>
              </div>

              {selectedTx.forensic_flags?.length > 0 && (
                <div className="mt-4 p-3 rounded bg-rose-950/30 border border-rose-500/30">
                  <span className="text-[10px] font-mono text-rose-400 font-bold block mb-1">
                    DETECTED STRUCTURING FLAGS:
                  </span>
                  <ul className="text-xs text-rose-200 space-y-1">
                    {selectedTx.forensic_flags.map((f, i) => (
                      <li key={i}>• {f}</li>
                    ))}
                  </ul>
                </div>
              )}
            </Card>
          )}

          {/* Shell Account Dispersion Nodes */}
          <Card className="p-4 border border-border-subtle bg-slate-900/50">
            <h3 className="text-sm font-bold tracking-wide text-cyan uppercase mb-3 flex items-center gap-2">
              <span>🌪️</span> Shell Dispersion Nodes
            </h3>
            <div className="space-y-2.5">
              {data?.shell_dispersion_accounts?.map((acc, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded bg-slate-800/50 border border-cyan/20 text-xs font-mono space-y-1"
                >
                  <div className="flex justify-between text-white font-bold">
                    <span>{acc.account_name}</span>
                    <span className="text-gold">₹{acc.total_volume.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-muted">
                    <span>Inflow: {acc.inflow_count} txs</span>
                    <span className="text-cyan font-bold">Outflow Fanout: {acc.outflow_fanout_count} accounts</span>
                  </div>
                  <span className="text-[10px] text-rose-400 font-bold block pt-1">
                    {acc.classification}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
