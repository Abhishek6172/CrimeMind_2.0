import React, { useState, useEffect } from "react";
import { Card, StatBox, Badge, Notice } from "../ui.jsx";
import { cyberAudio } from "../../utils/cyberAudio.js";

export function CvBenchmarkEvaluation() {
  const [data, setData] = useState(null);
  const [selectedConf, setSelectedConf] = useState("0.35");
  const [selectedModel, setSelectedModel] = useState("yolo11n");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/research/data/cv_evaluation_benchmark.json")
      .then((res) => res.json())
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Failed to load CV benchmark", err);
        setLoading(false);
      });
  }, []);

  if (loading) {
    return (
      <div className="state cm-loading-state">
        <div className="cm-radar-spinner" />
        <span>LOADING COMPUTER VISION BENCHMARK TELEMETRY…</span>
      </div>
    );
  }

  if (!data) {
    return <div className="state error">Failed to load CV benchmark data.</div>;
  }

  const modelY11 = data.models.find((m) => m.model_id === "yolo11n") || data.models[0];
  const modelY8 = data.models.find((m) => m.model_id === "yolov8n") || data.models[1];
  const activeModel = data.models.find((m) => m.model_id === selectedModel) || modelY11;
  const metrics = activeModel.metrics_by_conf[selectedConf];

  return (
    <div className="stack gap-4 font-mono">
      {/* Top Banner */}
      <div className="cm-cctv-banner">
        <div className="cm-cctv-banner-left">
          <span className="cm-pulse-cyan" />
          <strong className="text-white">SURVEILLANCE COMPUTER VISION & BYTETRACK MOT EVALUATION</strong>
          <Badge kind="EXPERIMENTAL">OFFICIAL BENCHMARK</Badge>
        </div>
        <div className="cm-cctv-banner-right small text-muted">
          DATASET: {data.benchmark_meta.dataset} · {data.benchmark_meta.total_test_frames} FRAMES
        </div>
      </div>

      {/* KPI Cards HUD */}
      <div className="cm-metrics-hud">
        <StatBox
          label="mAP @ 0.50 IoU"
          value={`${(metrics.map50 * 100).toFixed(1)}%`}
          sub={`@ Confidence threshold ${selectedConf}`}
          icon="🎯"
          accent="cyan"
        />
        <StatBox
          label="mAP @ 0.50:0.95"
          value={`${(metrics.map50_95 * 100).toFixed(1)}%`}
          sub="COCO standard strict localization"
          icon="📐"
          accent="amber"
        />
        <StatBox
          label="PRECISION / RECALL"
          value={`${(metrics.precision * 100).toFixed(1)}% / ${(metrics.recall * 100).toFixed(1)}%`}
          sub={`F1 Score: ${(2 * (metrics.precision * metrics.recall) / (metrics.precision + metrics.recall) * 100).toFixed(1)}%`}
          icon="⚖️"
          accent="emerald"
        />
        <StatBox
          label="CPU / GPU THROUGHPUT"
          value={`${metrics.fps_cpu.toFixed(0)} / ${metrics.fps_gpu.toFixed(0)} FPS`}
          sub={`Latency: ${metrics.latency_ms.toFixed(2)} ms / frame`}
          icon="⚡"
          accent="purple"
        />
      </div>

      <Notice level="info">
        Independent evaluation against 2,400 multi-camera surveillance frames. Benchmarks evaluate raw object detection (YOLO) and temporal tracking consistency (ByteTrack MOTA & ID stability).
      </Notice>

      {/* Interactive Controls Deck */}
      <div className="cm-money-controls-card">
        <div className="row items-center justify-between">
          <div className="row items-center gap-3">
            <span className="text-muted small">EVALUATE MODEL:</span>
            {data.models.map((m) => (
              <button
                key={m.model_id}
                className={`cm-filter-pill ${selectedModel === m.model_id ? "active" : ""}`}
                onClick={() => {
                  cyberAudio.playClickChirp();
                  setSelectedModel(m.model_id);
                }}
              >
                {m.name}
              </button>
            ))}
          </div>

          <div className="row items-center gap-2">
            <span className="text-muted small">CONFIDENCE THRESHOLD (τ):</span>
            {["0.25", "0.35", "0.50"].map((conf) => (
              <button
                key={conf}
                className={`cm-filter-pill ${selectedConf === conf ? "active" : ""}`}
                onClick={() => {
                  cyberAudio.playHoverBlip();
                  setSelectedConf(conf);
                }}
              >
                {conf}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Head-to-Head Comparison & Class Breakdown */}
      <div className="grid grid-2 gap-4">
        {/* Head to Head Comparison */}
        <Card title="Architecture Comparison: YOLOv11n vs YOLOv8n">
          <div className="tablewrap cm-cyber-tablewrap">
            <table className="cm-cyber-table small font-mono">
              <thead>
                <tr>
                  <th>METRIC (@ τ = {selectedConf})</th>
                  <th>YOLOv11n (Current)</th>
                  <th>YOLOv8n (Baseline)</th>
                  <th>DELTA (Δ)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>mAP @ 0.50</td>
                  <td className="text-cyan">{(modelY11.metrics_by_conf[selectedConf].map50 * 100).toFixed(1)}%</td>
                  <td>{(modelY8.metrics_by_conf[selectedConf].map50 * 100).toFixed(1)}%</td>
                  <td className="text-emerald">+{(modelY11.metrics_by_conf[selectedConf].map50 * 100 - modelY8.metrics_by_conf[selectedConf].map50 * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <td>mAP @ 0.50:0.95</td>
                  <td className="text-cyan">{(modelY11.metrics_by_conf[selectedConf].map50_95 * 100).toFixed(1)}%</td>
                  <td>{(modelY8.metrics_by_conf[selectedConf].map50_95 * 100).toFixed(1)}%</td>
                  <td className="text-emerald">+{(modelY11.metrics_by_conf[selectedConf].map50_95 * 100 - modelY8.metrics_by_conf[selectedConf].map50_95 * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <td>Detection Precision</td>
                  <td className="text-cyan">{(modelY11.metrics_by_conf[selectedConf].precision * 100).toFixed(1)}%</td>
                  <td>{(modelY8.metrics_by_conf[selectedConf].precision * 100).toFixed(1)}%</td>
                  <td className="text-emerald">+{(modelY11.metrics_by_conf[selectedConf].precision * 100 - modelY8.metrics_by_conf[selectedConf].precision * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <td>Detection Recall</td>
                  <td className="text-cyan">{(modelY11.metrics_by_conf[selectedConf].recall * 100).toFixed(1)}%</td>
                  <td>{(modelY8.metrics_by_conf[selectedConf].recall * 100).toFixed(1)}%</td>
                  <td className="text-emerald">+{(modelY11.metrics_by_conf[selectedConf].recall * 100 - modelY8.metrics_by_conf[selectedConf].recall * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <td>CPU Throughput</td>
                  <td className="text-cyan">{modelY11.metrics_by_conf[selectedConf].fps_cpu.toFixed(1)} FPS</td>
                  <td>{modelY8.metrics_by_conf[selectedConf].fps_cpu.toFixed(1)} FPS</td>
                  <td className="text-emerald">+{data.comparative_analysis.speedup_cpu_pct}%</td>
                </tr>
                <tr>
                  <td>GPU Throughput</td>
                  <td className="text-cyan">{modelY11.metrics_by_conf[selectedConf].fps_gpu.toFixed(1)} FPS</td>
                  <td>{modelY8.metrics_by_conf[selectedConf].fps_gpu.toFixed(1)} FPS</td>
                  <td className="text-emerald">+{data.comparative_analysis.speedup_gpu_pct}%</td>
                </tr>
                <tr>
                  <td>ByteTrack MOTA</td>
                  <td className="text-cyan">{(modelY11.tracking_metrics_bytetrack.mota * 100).toFixed(1)}%</td>
                  <td>{(modelY8.tracking_metrics_bytetrack.mota * 100).toFixed(1)}%</td>
                  <td className="text-emerald">+{(modelY11.tracking_metrics_bytetrack.mota * 100 - modelY8.tracking_metrics_bytetrack.mota * 100).toFixed(1)}%</td>
                </tr>
                <tr>
                  <td>ByteTrack ID Switches</td>
                  <td className="text-cyan">{modelY11.tracking_metrics_bytetrack.id_switches}</td>
                  <td>{modelY8.tracking_metrics_bytetrack.id_switches}</td>
                  <td className="text-emerald">-{data.comparative_analysis.id_switches_reduction_pct}% (Stable)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>

        {/* Per-Class CCTV Breakdown */}
        <Card title={`Per-Class Precision Breakdown (${activeModel.name})`}>
          <div className="tablewrap cm-cyber-tablewrap">
            <table className="cm-cyber-table small font-mono">
              <thead>
                <tr>
                  <th>OBJECT CLASS</th>
                  <th>SAMPLE INSTANCES</th>
                  <th>PRECISION</th>
                  <th>RECALL</th>
                  <th>mAP @ 0.50</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(activeModel.class_breakdown).map(([cls, stat]) => (
                  <tr key={cls}>
                    <td>
                      <Badge kind={cls === "person" ? "cyan" : "amber"}>{cls.toUpperCase()}</Badge>
                    </td>
                    <td>{stat.count.toLocaleString()}</td>
                    <td className="text-emerald">{(stat.precision * 100).toFixed(1)}%</td>
                    <td className="text-cyan">{(stat.recall * 100).toFixed(1)}%</td>
                    <td><b>{(stat.map50 * 100).toFixed(1)}%</b></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>

      {/* Formal Conclusion Summary Card */}
      <Card title="Scientific Evaluation Summary & Technical Takeaway">
        <blockquote className="cm-cyber-quote">
          {data.comparative_analysis.conclusion}
        </blockquote>
      </Card>
    </div>
  );
}
