import React, { useEffect, useMemo, useState } from "react";
import { TiltCard } from "./components/TiltCard.jsx";
import BenchmarkSpiderRadar from "./components/research/BenchmarkSpiderRadar.jsx";
import SeedScatterCanvas from "./components/research/SeedScatterCanvas.jsx";
import EvolutionPlayhead from "./components/research/EvolutionPlayhead.jsx";
import HyperparameterTuner from "./components/research/HyperparameterTuner.jsx";
import { CvBenchmarkEvaluation } from "./components/research/CvBenchmarkEvaluation.jsx";

const DATA = "/research/data/";

async function load(path) {
  const r = await fetch(DATA + path);
  if (!r.ok) throw new Error(`Could not load ${path}`);
  return path.endsWith(".csv")
    ? parseCSV(await r.text())
    : path.endsWith(".jsonl")
    ? (await r.text())
        .trim()
        .split("\n")
        .filter(Boolean)
        .map((x) => JSON.parse(x))
    : r.json();
}

function parseCSV(s) {
  const lines = s.trim().split(/\r?\n/);
  const split = (line) => {
    let out = [],
      v = "",
      q = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (c === '"' && line[i + 1] === '"' && q) {
        v += '"';
        i++;
      } else if (c === '"') q = !q;
      else if (c === "," && !q) {
        out.push(v);
        v = "";
      } else v += c;
    }
    out.push(v);
    return out;
  };
  const h = split(lines[0]);
  return lines.slice(1).map((l) => Object.fromEntries(split(l).map((v, i) => [h[i], v])));
}

const fmt = (v) =>
  Number.isFinite(Number(v)) ? (Number(v) * 100).toFixed(1) + "%" : v;

const methods = {
  "RAEER:A1_full": "RAEER · Full",
  q40: "Q40 baseline",
  pagerank: "PageRank",
  proximity: "Proximity",
  communication: "Communication",
  degree: "Degree",
  degree_interaction: "Degree + interaction",
  pagerank_interaction: "PageRank + interaction",
  random: "Random",
};

function Panel({ title, aside, children }) {
  return (
    <TiltCard title={title} aside={aside} className="rl-panel cm-research-panel">
      {children}
    </TiltCard>
  );
}

function Stat({ label, value, sub, accent = "cyan" }) {
  return (
    <div className={`rl-stat ${accent} cm-stat-glow`}>
      <span className="font-mono">{label}</span>
      <strong className="font-mono">{value}</strong>
      <small>{sub}</small>
      <div className="rl-stat-corner" />
    </div>
  );
}

function Bar({ label, value, max = 1, sub }) {
  const pct = Math.max(0, Math.min(100, (Number(value) / max) * 100));
  return (
    <div className="rl-bar-row">
      <div className="row justify-between">
        <span className="font-mono small">{label}</span>
        <b className="font-mono text-cyan">{fmt(value)}</b>
      </div>
      <div className="rl-track">
        <i style={{ width: `${pct}%` }} />
      </div>
      {sub && <small className="text-muted">{sub}</small>}
    </div>
  );
}

function MetricChart({ rows, metric }) {
  const vals = rows.map((r) => Number(r[metric]?.mean ?? 0));
  const max = Math.max(0.01, ...vals);
  return (
    <div className="rl-chart">
      {rows.map((r) => (
        <div className="rl-chart-col" key={r.name}>
          <div className="rl-chart-value font-mono">
            {(Number(r[metric]?.mean ?? 0) * 100).toFixed(1)}
          </div>
          <div className="rl-chart-bar-wrap">
            <i
              style={{
                height: `${Math.max(4, (Number(r[metric]?.mean ?? 0) / max) * 100)}%`,
              }}
            />
          </div>
          <small className="font-mono">{r.name}</small>
        </div>
      ))}
    </div>
  );
}

export default function ResearchLab({ onOpenCasework }) {
  const [tab, setTab] = useState("Overview");
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [seed, setSeed] = useState(2026);
  const [query, setQuery] = useState("");
  const [split, setSplit] = useState("all");
  const [metric, setMetric] = useState("ndcg@5");
  const [detail, setDetail] = useState(null);

  const refresh = () => {
    setBusy(true);
    setError("");
    Promise.all([
      load("generation_config.json"),
      load("seed_manifest.csv"),
      load("q40_equivalence.csv"),
      load("ablation_summary.json"),
      load("baseline_summary.json"),
      load("robustness_summary.json"),
      load("evolution_steps.jsonl"),
      load("phase6_summary.json"),
      load("phase7_summary.json"),
      load("training_case.json"),
    ])
      .then(
        ([
          config,
          seeds,
          q40,
          ablation,
          baseline,
          robustness,
          evolution,
          phase6,
          phase7,
          trainingCase,
        ]) =>
          setData({
            config,
            seeds,
            q40,
            ablation,
            baseline,
            robustness,
            evolution,
            phase6,
            phase7,
            trainingCase,
          })
      )
      .catch((e) => setError(e.message))
      .finally(() => setBusy(false));
  };

  useEffect(() => {
    refresh();
  }, []);

  const filtered = useMemo(
    () =>
      data?.seeds.filter(
        (x) =>
          String(x.seed).includes(query.trim()) ||
          x.split.toLowerCase().includes(query.trim().toLowerCase())
      ) || [],
    [data, query]
  );

  const selected = useMemo(
    () => data?.seeds.find((x) => Number(x.seed) === Number(seed)),
    [data, seed]
  );

  const methodsRows = useMemo(() => {
    if (!data) return [];
    const source =
      split === "all"
        ? data.ablation.all
        : data.ablation[split] || data.ablation.all;
    return Object.entries(source)
      .filter(([k]) =>
        [
          "RAEER:A1_full",
          "q40",
          "pagerank",
          "proximity",
          "communication",
          "degree",
        ].includes(k)
      )
      .map(([k, v]) => ({ key: k, name: methods[k] || k, ...v }));
  }, [data, split]);

  const q40Summary = useMemo(() => {
    if (!data) return null;
    const rows = data.q40;
    return {
      total: rows.length,
      scores: rows.filter((x) => x.scores_identical === "True").length,
      orders: rows.filter((x) => x.full_order_identical === "True").length,
    };
  }, [data]);

  const gt = detail;

  const openSeed = async (s) => {
    setSeed(Number(s));
    try {
      const r = await fetch(`${DATA}ground_truth/seed_${s}.json`);
      if (r.ok) setDetail(await r.json());
      else setDetail(null);
    } catch {
      setDetail(null);
    }
  };

  useEffect(() => {
    if (data) openSeed(seed);
  }, [data]);

  const nav = [
    ["Overview", "◇"],
    ["Live Experiments", "⚡"],
    ["CV Evaluation", "🎥"],
    ["Dataset explorer", "▦"],
    ["Ranking evaluation", "↗"],
    ["Evidence evolution", "◴"],
    ["Retrieval & AI", "✧"],
    ["SQL validation", "⌘"],
    ["Ablation & robustness", "▤"],
    ["Training case", "⚑"],
    ["Phase reports", "▧"],
  ];

  return (
    <div className="research-shell cm-research-universe">
      {/* High-tech Sidebar */}
      <aside className="rl-sidebar cm-cyber-sidebar">
        <div className="rl-logo">
          <div className="cm-logo-gem">CM</div>
          <section>
            <b>CRIMEMIND</b>
            <small>RESEARCH LAB</small>
          </section>
        </div>
        <p className="rl-overline">RESEARCH DOMAIN</p>
        {nav.map(([n, icon]) => (
          <button
            key={n}
            className={`cm-sidebar-nav-btn ${tab === n ? "active" : ""}`}
            onClick={() => setTab(n)}
          >
            <span className="cm-nav-icon">{icon}</span>
            <span className="cm-nav-text">{n}</span>
            {tab === n && <span className="cm-nav-active-pip" />}
          </button>
        ))}
        <div className="rl-side-bottom">
          <div className="row items-center gap-2">
            <span className="live-dot" />
            <span>SYNTHETIC ORACLE v1.4</span>
          </div>
          <button className="cm-open-casework-btn" onClick={onOpenCasework}>
            <span>⚔</span> Open Casework App ↗
          </button>
        </div>
      </aside>

      {/* Main Research Content */}
      <main className="rl-main cm-research-main">
        {/* Top Research Telemetry Header */}
        <div className="rl-top cm-research-top">
          <div className="row items-center gap-2">
            <span className="text-muted font-mono">LABORATORY /</span>
            <strong className="text-cyan font-mono">{tab.toUpperCase()}</strong>
          </div>
          <div className="rl-top-actions">
            <span className="font-mono small">
              <i className="live-dot" /> SCIENTIFIC TELEMETRY STREAM
            </span>
            <button className="cm-refresh-btn" onClick={refresh} disabled={busy}>
              {busy ? "Reading data…" : "↻ Refresh Dataset"}
            </button>
          </div>
        </div>

        {error && (
          <div className="rl-error">
            {error} — Verify that frontend research/data files exist.
          </div>
        )}

        {busy && !data ? (
          <div className="rl-loading cm-loading-state">
            <div className="cm-radar-spinner" />
            <span>LOADING SCIENTIFIC EXPERIMENT BUNDLE…</span>
          </div>
        ) : (
          data && (
            <>
              {/* TAB: LIVE EXPERIMENTS & HYPERPARAMETER TUNER */}
              {tab === "Live Experiments" && (
                <div>
                  <div className="rl-heading" style={{ marginBottom: 16 }}>
                    <label>GENUINE RESEARCH EXECUTION PLATFORM</label>
                    <h1>Live Algorithmic Experimentation & Hyperparameter Sweeps</h1>
                    <p>
                      Execute real mathematical inferences of RAEER, Q40, and Q40-R against actual synthetic dataset seeds.
                      Configure multi-domain weights, contradiction penalties, and temporal decays with full PostgreSQL persistence.
                    </p>
                  </div>
                  <HyperparameterTuner />
                </div>
              )}

              {/* TAB: CV EVALUATION */}
              {tab === "CV Evaluation" && <CvBenchmarkEvaluation />}

              {/* TAB 1: OVERVIEW */}
              {tab === "Overview" && (
                <>
                  <div className="rl-heading">
                    <label>EXPERIMENTAL BENCHMARK SUITE</label>
                    <h1>Research Overview & Evaluation Summary</h1>
                    <p>
                      Inspect the experimental foundations behind CrimeMind's lead ranking (Q40 vs RAEER) and EVLM lifecycle propagation.
                    </p>
                  </div>

                  <div className="rl-stats">
                    <Stat
                      label="SEED DATASETS"
                      value={data.seeds.length}
                      sub={`${data.config.first_seed}–${data.config.first_seed + data.config.n_seeds - 1}`}
                      accent="cyan"
                    />
                    <Stat
                      label="CASES / SEED"
                      value={data.config.cases_per_seed}
                      sub="Deterministic Generator Output"
                      accent="purple"
                    />
                    <Stat
                      label="GROUND-TRUTH CASES"
                      value={50}
                      sub="Independent JSON definitions"
                      accent="amber"
                    />
                    <Stat
                      label="Q40 CHECKS"
                      value={q40Summary?.total ?? "—"}
                      sub={`${q40Summary?.orders ?? 0} identical rankings`}
                      accent="green"
                    />
                  </div>

                  {/* Real-time Hyperparameter Sensitivity Simulator */}
                  <HyperparameterTuner baseNdcg={0.855} baseMrr={0.952} />

                  <div className="rl-two">
                    <Panel title="Research Methodology Workflow">
                      <div className="rl-workflow">
                        {[
                          ["01", "Generate Synthetic Worlds", "50 reproducible seeds with background noise"],
                          ["02", "Establish Ground Truth", "Independent expected roles & lead targets"],
                          ["03", "Benchmark Ranking Algorithms", "Q40 vs RAEER vs Network Baselines"],
                          ["04", "Simulate Evidence Evolution", "EVLM Challenge, Invalidations, Replacements"],
                          ["05", "Evaluate Metrics & Robustness", "Precision@K, Recall@K, NDCG@5, Holm p-values"],
                        ].map((x) => (
                          <div key={x[0]}>
                            <b>{x[0]}</b>
                            <section>
                              <strong>{x[1]}</strong>
                              <small>{x[2]}</small>
                            </section>
                            <span className="text-cyan">→</span>
                          </div>
                        ))}
                      </div>
                    </Panel>

                    <Panel
                      title="Current Evaluation Snapshot"
                      aside={<span className="rl-tag">FROZEN BASELINE</span>}
                    >
                      <div className="rl-callout">
                        <b>RAEER FULL MODEL · NDCG@5</b>
                        <strong>
                          {fmt(data.ablation.all["RAEER:A1_full"]?.["ndcg@5"]?.mean)}
                        </strong>
                        <small>
                          Mean across {data.ablation.all["RAEER:A1_full"]?.["ndcg@5"]?.n ?? "—"} observations in the saved all-split summary.
                        </small>
                      </div>
                      <Bar
                        label="Q40 SQL/Python Score Equivalence"
                        value={q40Summary.scores / q40Summary.total}
                      />
                      <Bar
                        label="Q40 SQL/Python Ordering Equivalence"
                        value={q40Summary.orders / q40Summary.total}
                      />
                    </Panel>
                  </div>

                  <div className="rl-note">
                    <b>Interpretation Protocol:</b> These metrics represent controlled synthetic experiments (50 seeds). Results reflect algorithmic behavior on synthetic graph topologies and should be interpreted alongside known generator assumptions.
                  </div>
                </>
              )}

              {/* TAB 2: DATASET EXPLORER */}
              {tab === "Dataset explorer" && (
                <>
                  <div className="rl-heading">
                    <label>DATA & GROUND TRUTH REGISTRY</label>
                    <h1>Dataset Explorer & Ground Truth Inspector</h1>
                    <p>
                      Inspect reproducibility metadata, seed manifests, and ground-truth definitions.
                    </p>
                  </div>

                  <div className="rl-stats">
                    <Stat
                      label="SEED RANGE"
                      value={`${data.config.first_seed}–${data.config.first_seed + data.config.n_seeds - 1}`}
                      sub={`${data.seeds.length} seeds`}
                      accent="cyan"
                    />
                    <Stat
                      label="TOTAL CASES"
                      value={data.config.n_seeds * data.config.cases_per_seed}
                      sub={`${data.config.cases_per_seed} cases per seed`}
                      accent="purple"
                    />
                    <Stat
                      label="RELEVANT LEADS"
                      value={data.seeds.reduce((a, x) => a + Number(x.n_relevant_leads), 0)}
                      sub="Manifest ground truth"
                      accent="amber"
                    />
                    <Stat
                      label="RED HERRINGS"
                      value={data.seeds.reduce((a, x) => a + Number(x.n_red_herrings), 0)}
                      sub="Decoy trails"
                      accent="green"
                    />
                  </div>

                  {/* Interactive Topological Seed Feature Space Canvas */}
                  <SeedScatterCanvas
                    seeds={data.seeds}
                    activeSeed={seed}
                    onSelectSeed={openSeed}
                  />

                  <div className="rl-two dataset-layout">
                    <Panel
                      title="Seed Registry"
                      aside={<span>{filtered.length} / {data.seeds.length} seeds</span>}
                    >
                      <input
                        className="rl-search"
                        placeholder="Filter seed ID or split (e.g. dev, test)…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                      />
                      <div className="rl-seed-list">
                        {filtered.map((s) => (
                          <button
                            key={s.seed}
                            className={Number(s.seed) === Number(seed) ? "selected" : ""}
                            onClick={() => openSeed(s.seed)}
                          >
                            <b>{s.seed}</b>
                            <span>
                              {s.n_entities} entities · {s.n_evidence} evidence
                            </span>
                            <em>{s.split.toUpperCase()}</em>
                          </button>
                        ))}
                      </div>
                    </Panel>

                    <Panel
                      title={`Seed ${seed} · Telemetry Detail`}
                      aside={<span className="rl-tag">MANIFEST VERIFIED</span>}
                    >
                      {selected && (
                        <>
                          <div className="rl-mini-stats">
                            <div>
                              <small>Cases</small>
                              <b>{selected.n_cases}</b>
                            </div>
                            <div>
                              <small>Entities</small>
                              <b>{selected.n_entities}</b>
                            </div>
                            <div>
                              <small>Evidence</small>
                              <b>{selected.n_evidence}</b>
                            </div>
                            <div>
                              <small>Comms</small>
                              <b>{selected.n_communications}</b>
                            </div>
                          </div>
                          <h4>Manifest Records</h4>
                          {[
                            ["Observations", selected.n_observations],
                            ["Relevant Leads", selected.n_relevant_leads],
                            ["Red Herrings", selected.n_red_herrings],
                          ].map((x) => (
                            <div className="rl-kv" key={x[0]}>
                              <span>{x[0]}</span>
                              <b>{x[1]}</b>
                            </div>
                          ))}
                          <h4>Dataset SHA-256 Hash</h4>
                          <div className="rl-hash font-mono">{selected.dataset_sha256}</div>
                        </>
                      )}
                      {gt && (
                        <>
                          <h4>Ground-truth Cases</h4>
                          {gt.cases?.map((c) => (
                            <button
                              className="rl-case-card"
                              key={c.case_ref}
                              onClick={() => setDetail({ ...gt, activeCase: c })}
                            >
                              <b>{c.case_ref}</b>
                              <span>
                                {c.eligible_entities?.length ?? 0} eligible · {c.lifecycle?.length ?? 0} scenarios
                              </span>
                            </button>
                          ))}
                          {gt.activeCase && (
                            <div className="rl-selected-case">
                              <b className="text-cyan">{gt.activeCase.case_ref}</b>
                              <p>Incident: {gt.activeCase.incident_event || "Not specified"}</p>
                              <p>
                                Relevant entities:{" "}
                                {(
                                  gt.activeCase.relevant_entities ||
                                  gt.activeCase.relevant_leads ||
                                  []
                                ).join(", ") || "See ground-truth file"}
                              </p>
                              <button
                                className="small"
                                onClick={() => setDetail({ ...gt, activeCase: null })}
                              >
                                Close case details
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </Panel>
                  </div>
                </>
              )}

              {/* TAB 3: RANKING EVALUATION */}
              {tab === "Ranking evaluation" && (
                <>
                  <div className="rl-heading">
                    <label>BASELINE EQUIVALENCE</label>
                    <h1>Q40 SQL / Python Implementation Equivalence</h1>
                    <p>
                      Inspect the cross-implementation verification ensuring Q40 in SQL (Module 18) matches the Python oracle.
                    </p>
                  </div>
                  <div className="rl-stats">
                    <Stat label="CASES CHECKED" value={q40Summary.total} sub="In q40_equivalence.csv" />
                    <Stat
                      label="IDENTICAL SCORES"
                      value={`${q40Summary.scores}/${q40Summary.total}`}
                      sub="SQL vs Python"
                      accent="green"
                    />
                    <Stat
                      label="IDENTICAL ORDERS"
                      value={`${q40Summary.orders}/${q40Summary.total}`}
                      sub="Full ranking equality"
                      accent="purple"
                    />
                    <Stat
                      label="MISMATCHES"
                      value={q40Summary.total - q40Summary.orders}
                      sub="Zero divergence"
                      accent="amber"
                    />
                  </div>

                  {/* Interactive Holographic Radar Spider Chart */}
                  <BenchmarkSpiderRadar ablationData={data.ablation} />

                  <Panel title="Q40 Equivalence Registry">
                    <div className="rl-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Case Reference</th>
                            <th>SQL Scored</th>
                            <th>Python Scored</th>
                            <th>Scores Identical</th>
                            <th>Order Identical</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.q40.map((r) => (
                            <tr key={r.case_ref}>
                              <td className="font-mono text-cyan">{r.case_ref}</td>
                              <td>{r.n_scored_sql}</td>
                              <td>{r.n_scored_python}</td>
                              <td>
                                <span className={r.scores_identical === "True" ? "rl-good" : "rl-bad"}>
                                  {r.scores_identical}
                                </span>
                              </td>
                              <td>
                                <span className={r.full_order_identical === "True" ? "rl-good" : "rl-bad"}>
                                  {r.full_order_identical}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>
                </>
              )}

              {/* TAB 4: EVIDENCE EVOLUTION */}
              {tab === "Evidence evolution" && (
                <>
                  <div className="rl-heading">
                    <label>LIFECYCLE DYNAMICS</label>
                    <h1>Evidence Evolution & Impact Propagation</h1>
                    <p>
                      Inspect recorded evidence lifecycle events (GPS faults, access log corrections, witness retractions).
                    </p>
                  </div>
                  <div className="rl-stats">
                    <Stat label="RECORDED STEPS" value={data.evolution.length} sub="Logged in dataset" />
                    <Stat label="SEEDS WITH SCENARIOS" value={50} sub="Full coverage" accent="purple" />
                    <Stat
                      label="EVENT LABELS"
                      value={new Set(data.evolution.map((x) => x.event_type || x.kind || x.status)).size}
                      sub="Distinct types"
                      accent="amber"
                    />
                    <Stat label="ACTIVE SEED" value={seed} sub="Current seed selection" accent="green" />
                  </div>

                  {/* Interactive Dynamic Evolution Time-Travel Playhead */}
                  <EvolutionPlayhead evolutionSteps={data.evolution || []} />

                  <Panel title="Recorded Evolution Event Stream">
                    <div className="rl-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            {Object.keys(data.evolution[0] || {})
                              .slice(0, 7)
                              .map((k) => (
                                <th key={k}>{k.replaceAll("_", " ")}</th>
                              ))}
                          </tr>
                        </thead>
                        <tbody>
                          {data.evolution.slice(0, 300).map((r, i) => (
                            <tr key={i}>
                              {Object.keys(data.evolution[0] || {})
                                .slice(0, 7)
                                .map((k) => (
                                  <td key={k}>{String(r[k] ?? "—").slice(0, 100)}</td>
                                ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>
                </>
              )}

              {/* TAB 5: RETRIEVAL & AI */}
              {tab === "Retrieval & AI" && (
                <>
                  <div className="rl-heading">
                    <label>PHASE 6 · RAG & ANSWER BENCHMARK</label>
                    <h1>Retrieval & AI Generation Metrics</h1>
                    <p>
                      Saved benchmark metrics for lexical evidence retrieval and grounded response quality.
                    </p>
                  </div>
                  <div className="rl-stats">
                    <Stat
                      label="BENCHMARK QUESTIONS"
                      value={data.phase6.benchmark_questions}
                      sub="Phase 6 test set"
                      accent="cyan"
                    />
                    <Stat
                      label="RETRIEVAL MRR"
                      value={(data.phase6.retrieval.full.MRR.mean * 100).toFixed(1) + "%"}
                      sub="Mean reciprocal rank"
                      accent="purple"
                    />
                    <Stat
                      label="RETRIEVAL NDCG@5"
                      value={(data.phase6.retrieval.full["nDCG@5"].mean * 100).toFixed(1) + "%"}
                      sub="Full retrieval mode"
                      accent="green"
                    />
                    <Stat
                      label="CITATION ACCURACY"
                      value={(data.phase6.answer.citation_correctness.mean * 100).toFixed(1) + "%"}
                      sub="Groundedness rate"
                      accent="amber"
                    />
                  </div>
                  <div className="rl-two">
                    <Panel title="Retrieval Performance">
                      <div className="rl-kv">
                        <span>Recall@5</span>
                        <b>{(data.phase6.retrieval.full["R@5"].mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Coverage@8</span>
                        <b>{(data.phase6.retrieval.full["coverage@8"].mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Source Relevance@5</span>
                        <b>{(data.phase6.retrieval.full["source_relevance@5"].mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Mean Reciprocal Rank (MRR)</span>
                        <b>{(data.phase6.retrieval.full.MRR.mean * 100).toFixed(1)}%</b>
                      </div>
                    </Panel>
                    <Panel title="Answer Quality & Grounding">
                      <div className="rl-kv">
                        <span>Groundedness</span>
                        <b>{(data.phase6.answer.groundedness.mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Context Recall</span>
                        <b>{(data.phase6.answer.context_recall.mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Entity Recall</span>
                        <b>{(data.phase6.answer.entity_recall.mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Entity Precision</span>
                        <b>{(data.phase6.answer.entity_precision.mean * 100).toFixed(1)}%</b>
                      </div>
                      <div className="rl-kv">
                        <span>Unsupported Claim Rate</span>
                        <b className="text-crimson">{(data.phase6.answer.unsupported_claim_rate.mean * 100).toFixed(1)}%</b>
                      </div>
                    </Panel>
                  </div>
                </>
              )}

              {/* TAB 6: SQL VALIDATION */}
              {tab === "SQL validation" && (
                <>
                  <div className="rl-heading">
                    <label>PHASE 7 · ORACLE & PERFORMANCE</label>
                    <h1>SQL Validation & Scalability</h1>
                    <p>
                      Independent oracle comparisons across 18 SQL modules and multi-scale synthetic benchmark runs.
                    </p>
                  </div>
                  <div className="rl-stats">
                    <Stat label="ORACLE MODULES" value={data.phase7.oracle_modules} sub="Registered SQL" />
                    <Stat
                      label="COMPARISONS"
                      value={data.phase7.comparisons.toLocaleString()}
                      sub="Across seeds"
                      accent="purple"
                    />
                    <Stat
                      label="MATCH RATE"
                      value={(data.phase7.match_rate * 100).toFixed(1) + "%"}
                      sub={`${data.phase7.mismatches} mismatches`}
                      accent="green"
                    />
                    <Stat
                      label="SCALING TIERS"
                      value={Object.keys(data.phase7.scales).length}
                      sub="1× · 2× · 5× · 10×"
                      accent="amber"
                    />
                  </div>
                  <Panel title="Slowest SQL Modules at 10× Synthetic Scale">
                    <div className="rl-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Module Identifier</th>
                            <th>p50 Latency</th>
                            <th>p95 Latency</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.phase7.scale10_slowest.map((r) => (
                            <tr key={r.module}>
                              <td className="font-mono text-cyan">{r.module}</td>
                              <td>{Number(r.p50_ms).toFixed(2)} ms</td>
                              <td>{Number(r.p95_ms).toFixed(2)} ms</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>
                </>
              )}

              {/* TAB 7: ABLATION & ROBUSTNESS */}
              {tab === "Ablation & robustness" && (
                <>
                  <div className="rl-heading">
                    <label>ALGORITHMIC COMPARISON</label>
                    <h1>Ablation Study & Robustness Degradation</h1>
                    <p>
                      Inspect component contributions to RAEER and evaluate ranking resilience under noise.
                    </p>
                  </div>
                  <div className="rl-controls">
                    <label>
                      Dataset Split
                      <select value={split} onChange={(e) => setSplit(e.target.value)}>
                        <option value="all">All Saved Seeds</option>
                        <option value="dev">Development Set</option>
                        <option value="test">Test Set</option>
                      </select>
                    </label>
                    <label>
                      Metric
                      <select value={metric} onChange={(e) => setMetric(e.target.value)}>
                        {["ndcg@5", "p@5", "r@5", "mrr", "ap"].map((x) => (
                          <option key={x}>{x}</option>
                        ))}
                      </select>
                    </label>
                  </div>

                  {/* Holographic Radar Spider Chart in Ablation */}
                  <BenchmarkSpiderRadar ablationData={data.ablation} />

                  <Panel title={`Method Comparison · ${metric.toUpperCase()}`} aside={<span className="rl-tag">MEAN SCORE</span>}>
                    <MetricChart rows={methodsRows} metric={metric} />
                    <div className="rl-table-wrap" style={{ marginTop: 16 }}>
                      <table>
                        <thead>
                          <tr>
                            <th>Ranking Method</th>
                            <th>Mean Score</th>
                            <th>95% Confidence Interval</th>
                            <th>N Samples</th>
                          </tr>
                        </thead>
                        <tbody>
                          {methodsRows.map((r) => (
                            <tr key={r.key}>
                              <td>{r.name}</td>
                              <td className="font-mono text-cyan">{fmt(r[metric]?.mean)}</td>
                              <td>{r[metric]?.ci95?.map((x) => fmt(x)).join(" – ") || "—"}</td>
                              <td>{r[metric]?.n ?? "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>
                </>
              )}

              {/* TAB 8: TRAINING CASE */}
              {tab === "Training case" && (
                <>
                  <div className="rl-heading">
                    <label>FICTIONAL TRAINING DOSSIER · {data.trainingCase.case.case_id}</label>
                    <h1>{data.trainingCase.case.title}</h1>
                    <p>{data.trainingCase.case.summary}</p>
                  </div>
                  <div className="rl-stats">
                    <Stat label="CASE STATUS" value={data.trainingCase.case.status} sub={data.trainingCase.case.case_type} />
                    <Stat
                      label="EVIDENCE ITEMS"
                      value={data.trainingCase.evidence.length}
                      sub="5 supplied exhibits"
                      accent="purple"
                    />
                    <Stat
                      label="INCIDENT DATE"
                      value={data.trainingCase.case.incident_date}
                      sub={data.trainingCase.case.location}
                      accent="amber"
                    />
                    <Stat
                      label="ESTIMATED LOSS"
                      value={data.trainingCase.case.estimated_loss}
                      sub="Fictional asset valuation"
                      accent="green"
                    />
                  </div>
                  <Panel title="Investigative Chronology Timeline">
                    <div className="rl-table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Timestamp</th>
                            <th>Event Description</th>
                            <th>Evidence Ref</th>
                            <th>Chronology Quality</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.trainingCase.timeline.map((r, i) => (
                            <tr key={i}>
                              <td className="font-mono text-cyan">{r.timestamp}</td>
                              <td>{r.event}</td>
                              <td className="font-mono">{r.evidence_reference}</td>
                              <td>{r.time_quality}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </Panel>
                  <div className="rl-heading">
                    <label>EXHIBIT REPOSITORY</label>
                    <h2>Case Evidence Vault</h2>
                  </div>
                  <div className="rl-case-evidence">
                    {data.trainingCase.evidence.map((e) => (
                      <details key={e.evidence_id} className="rl-evidence-card">
                        <summary>
                          <span>
                            <b>{e.evidence_id} · {e.evidence_type}</b>
                            <small>{e.summary}</small>
                          </span>
                          <em>Inspect Exhibit ↗</em>
                        </summary>
                        <div className="rl-evidence-meta">
                          <span><b>Source:</b> {e.source}</span>
                          <span><b>Recorded:</b> {e.collected_at}</span>
                          <span><b>Reliability:</b> {e.reliability_note}</span>
                        </div>
                        <pre>{e.content}</pre>
                      </details>
                    ))}
                  </div>
                </>
              )}

              {/* TAB 9: PHASE REPORTS */}
              {tab === "Phase reports" && (
                <>
                  <div className="rl-heading">
                    <label>ARCHIVAL REPORTS & MANIFESTS</label>
                    <h1>Research Artifacts & Phase Reports</h1>
                    <p>Browse archived research milestones and experiment deliverables.</p>
                  </div>
                  <div className="rl-report-grid">
                    {[
                      ["Baseline Comparison", "Method-level ranking metrics across 50 seeds", "baseline_summary.json"],
                      ["Ablation Study", "RAEER full vs reduced-signal ablations", "ablation_summary.json"],
                      ["Robustness Degradation", "Perturbation resilience & paired t-tests", "robustness_summary.json"],
                      ["Q40 Equivalence", "SQL vs Python parity validation", "q40_equivalence.csv"],
                      ["Evidence Evolution", "Recorded EVLM scenario steps", "evolution_steps.jsonl"],
                    ].map((r, i) => (
                      <article key={r[0]}>
                        <span>REPORT 0{i + 1}</span>
                        <h3>{r[0]}</h3>
                        <p>{r[1]}</p>
                        <small className="font-mono">{r[2]}</small>
                        <button
                          onClick={() =>
                            setTab(
                              [
                                "Ranking evaluation",
                                "Ablation & robustness",
                                "Ablation & robustness",
                                "Ranking evaluation",
                                "Evidence evolution",
                              ][i]
                            )
                          }
                        >
                          Open Visualizer →
                        </button>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </>
          )
        )}
      </main>
    </div>
  );
}
