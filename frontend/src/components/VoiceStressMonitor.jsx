import React, { useState, useEffect, useRef } from "react";
import { Card, Badge, StatBox } from "./ui.jsx";
import { cyberAudio } from "../utils/cyberAudio.js";
import { api } from "../api.js";

/**
 * Autocorrelation algorithm for fundamental frequency (Pitch F0) extraction.
 * Returns pitch in Hz, or -1 if unvoiced/silent.
 */
function autoCorrelate(buffer, sampleRate) {
  const SIZE = buffer.length;
  let rms = 0;

  for (let i = 0; i < SIZE; i++) {
    const val = buffer[i];
    rms += val * val;
  }
  rms = Math.sqrt(rms / SIZE);

  // If signal is too quiet, it's silence/unvoiced
  if (rms < 0.015) return -1;

  let r1 = 0;
  let r2 = SIZE - 1;
  const thres = 0.2;

  // Trim edges where signal is weak
  for (let i = 0; i < SIZE / 2; i++) {
    if (Math.abs(buffer[i]) < thres) {
      r1 = i;
      break;
    }
  }
  for (let i = 1; i < SIZE / 2; i++) {
    if (Math.abs(buffer[SIZE - i]) < thres) {
      r2 = SIZE - i;
      break;
    }
  }

  const trimmed = buffer.slice(r1, r2);
  const c = new Array(trimmed.length).fill(0);

  for (let i = 0; i < trimmed.length; i++) {
    for (let j = 0; j < trimmed.length - i; j++) {
      c[i] = c[i] + trimmed[j] * trimmed[j + i];
    }
  }

  let d = 0;
  while (c[d] > c[d + 1]) d++;

  let maxval = -1;
  let maxpos = -1;
  for (let i = d; i < trimmed.length; i++) {
    if (c[i] > maxval) {
      maxval = c[i];
      maxpos = i;
    }
  }

  let T0 = maxpos;
  // Parabolic interpolation for fine sub-sample peak localization
  const x1 = c[T0 - 1];
  const x2 = c[T0];
  const x3 = c[T0 + 1];
  const a = (x1 + x3 - 2 * x2) / 2;
  const b = (x3 - x1) / 2;
  if (a) T0 = T0 - b / (2 * a);

  const freq = sampleRate / T0;
  // Plausible human vocal range: 75 Hz (deep bass) to 500 Hz (high soprano)
  if (freq >= 75 && freq <= 500) {
    return freq;
  }
  return -1;
}

export function VoiceStressMonitor({ caseRef, onLogToCase, onClose }) {
  const [isActive, setIsActive] = useState(false);
  const [permissionError, setPermissionError] = useState(null);

  // Live Metrics State
  const [currentPitch, setCurrentPitch] = useState(0);
  const [currentDecibels, setCurrentDecibels] = useState(-60);
  const [currentJitter, setCurrentJitter] = useState(0.8);
  const [stressScore, setStressScore] = useState(20);
  const [peakStress, setPeakStress] = useState(20);
  const [stressLevel, setStressLevel] = useState("BASELINE / CALM");
  const [hesitationCount, setHesitationCount] = useState(0);
  const [isRecordingStatement, setIsRecordingStatement] = useState(false);

  // Live Speech Transcription
  const [liveTranscript, setLiveTranscript] = useState("");
  const [transcriptLog, setTranscriptLog] = useState([]);
  const [interrogateSubject, setInterrogateSubject] = useState("Suspect");
  const [isCommitting, setIsCommitting] = useState(false);

  // Audio Graph References
  const audioCtxRef = useRef(null);
  const analyserRef = useRef(null);
  const mediaStreamRef = useRef(null);
  const animFrameRef = useRef(null);
  const recognitionRef = useRef(null);

  // Canvas Refs
  const waveformCanvasRef = useRef(null);
  const stressCanvasRef = useRef(null);
  const stressHistoryRef = useRef(new Array(80).fill(20));
  const recentPitchesRef = useRef([]);
  const silenceTimerRef = useRef(0);

  // Start Real-Time Microphone Interrogation
  const startAudioInterrogation = async () => {
    setPermissionError(null);
    try {
      cyberAudio?.playScan?.();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: false, // keep natural vocal tremor harmonics
          autoGainControl: false,
        },
      });

      mediaStreamRef.current = stream;
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const audioCtx = new AudioContext();
      audioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 2048;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);
      analyserRef.current = analyser;

      setIsActive(true);

      // Start Speech Recognition if supported
      startSpeechRecognition();
    } catch (err) {
      console.error("Microphone access failed", err);
      setPermissionError(
        "Microphone permission denied or audio device unavailable. Please allow microphone access in your browser."
      );
    }
  };

  // Stop Interrogation
  const stopAudioInterrogation = () => {
    setIsActive(false);
    if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach((t) => t.stop());
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
      audioCtxRef.current.close().catch(() => {});
    }
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch {}
    }
  };

  // Setup Web Speech API for live transcription
  const startSpeechRecognition = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    try {
      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onresult = (event) => {
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            const finalTxt = event.results[i][0].transcript.trim();
            if (finalTxt) {
              setTranscriptLog((prev) => [
                ...prev,
                {
                  text: finalTxt,
                  stress: stressScore,
                  timestamp: new Date().toLocaleTimeString(),
                },
              ]);
            }
          } else {
            interim += event.results[i][0].transcript;
          }
        }
        setLiveTranscript(interim);
      };

      recognition.onerror = () => {};
      recognition.onend = () => {
        if (isActive) {
          try { recognition.start(); } catch {}
        }
      };

      recognition.start();
      recognitionRef.current = recognition;
    } catch (e) {
      console.warn("Speech recognition not active:", e);
    }
  };

  // 60 FPS Real-Time Acoustic Processing & Canvas Loop
  useEffect(() => {
    if (!isActive || !analyserRef.current) return;

    const analyser = analyserRef.current;
    const audioCtx = audioCtxRef.current;
    const timeDomain = new Float32Array(analyser.fftSize);
    const freqDomain = new Uint8Array(analyser.frequencyBinCount);

    const processFrame = () => {
      analyser.getFloatTimeDomainData(timeDomain);
      analyser.getByteFrequencyData(freqDomain);

      // 1. RMS Decibels Calculation
      let sum = 0;
      for (let i = 0; i < timeDomain.length; i++) {
        sum += timeDomain[i] * timeDomain[i];
      }
      const rms = Math.sqrt(sum / timeDomain.length);
      const db = Math.max(-60, Math.round(20 * Math.log10(rms + 1e-6)));
      setCurrentDecibels(db);

      // 2. Fundamental Frequency Pitch Extraction (Autocorrelation)
      const pitch = autoCorrelate(timeDomain, audioCtx.sampleRate);

      if (pitch > 0) {
        setCurrentPitch(Math.round(pitch));
        recentPitchesRef.current.push(pitch);
        if (recentPitchesRef.current.length > 25) {
          recentPitchesRef.current.shift();
        }
        silenceTimerRef.current = 0;
      } else {
        // Track prolonged hesitations
        silenceTimerRef.current += 1;
        if (silenceTimerRef.current === 60) {
          // ~1 second silence during conversation
          setHesitationCount((c) => c + 1);
        }
      }

      // 3. Pitch Jitter (Vocal Micro-Tremor Calculation)
      let jitterPct = 0.8;
      const pitches = recentPitchesRef.current;
      if (pitches.length >= 8) {
        let diffSum = 0;
        let avgPitch = 0;
        for (let i = 0; i < pitches.length; i++) {
          avgPitch += pitches[i];
          if (i > 0) diffSum += Math.abs(pitches[i] - pitches[i - 1]);
        }
        avgPitch /= pitches.length;
        const avgDiff = diffSum / (pitches.length - 1);
        jitterPct = (avgDiff / avgPitch) * 100;
        setCurrentJitter(parseFloat(jitterPct.toFixed(2)));
      }

      // 4. Composite Computer Voice Stress Index (0 - 100%)
      // High jitter (>2.0%) + volume instability + high pitch shift = high stress
      let computedStress = 20;
      if (pitch > 0) {
        // Baseline pitch expected ~ 120-190 Hz; sudden sharp spikes indicate strain
        const pitchStrain = Math.min(40, Math.abs(pitch - 145) * 0.4);
        const tremorStrain = Math.min(45, (jitterPct - 0.7) * 18);
        const volStrain = Math.min(15, Math.abs(db + 25) * 0.8);
        computedStress = Math.max(10, Math.min(99, Math.round(15 + pitchStrain + tremorStrain + volStrain)));
      } else {
        computedStress = Math.max(15, Math.round(stressScore * 0.95)); // smooth decay during silence
      }

      setStressScore(computedStress);
      setPeakStress((prev) => Math.max(prev, computedStress));

      if (computedStress >= 68) {
        setStressLevel("ELEVATED STRESS / DECEPTION INDICATOR [!]");
      } else if (computedStress >= 42) {
        setStressLevel("MILD COGNITIVE HESITATION");
      } else {
        setStressLevel("BASELINE / CALM");
      }

      // Append to history buffer for scrolling graph
      stressHistoryRef.current.push(computedStress);
      stressHistoryRef.current.shift();

      // 5. Draw Live Oscilloscope Spectrum Waveform
      drawWaveform(timeDomain, freqDomain);

      // 6. Draw Scrolling Stress Telemetry Line Graph
      drawStressGraph();

      animFrameRef.current = requestAnimationFrame(processFrame);
    };

    animFrameRef.current = requestAnimationFrame(processFrame);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [isActive]);

  // Render Real-Time Oscilloscope Waveform Canvas
  const drawWaveform = (timeDomain, freqDomain) => {
    const canvas = waveformCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Spectrum Bars in Background
    const bars = 48;
    const barW = w / bars;
    for (let i = 0; i < bars; i++) {
      const freqVal = freqDomain[i * 2] || 0;
      const barH = (freqVal / 255) * (h * 0.75);
      const grad = ctx.createLinearGradient(0, h, 0, h - barH);
      grad.addColorStop(0, "rgba(6, 182, 212, 0.2)");
      grad.addColorStop(1, "rgba(245, 158, 11, 0.4)");
      ctx.fillStyle = grad;
      ctx.fillRect(i * barW, h - barH, barW - 1, barH);
    }

    // Oscilloscope Green Audio Line in Foreground
    ctx.lineWidth = 2;
    ctx.strokeStyle = stressScore > 65 ? "#F43F5E" : stressScore > 40 ? "#F59E0B" : "#10B981";
    ctx.beginPath();

    const sliceW = w / timeDomain.length;
    let x = 0;
    for (let i = 0; i < timeDomain.length; i++) {
      const v = timeDomain[i];
      const y = (0.5 + v * 0.45) * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += sliceW;
    }
    ctx.stroke();
  };

  // Render Scrolling 60 FPS Stress Telemetry Graph
  const drawStressGraph = () => {
    const canvas = stressCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    // Grid lines for 30%, 60%, 80% stress zones
    ctx.strokeStyle = "rgba(30, 58, 95, 0.4)";
    ctx.lineWidth = 1;
    [0.35, 0.65].forEach((zone) => {
      const y = h - h * zone;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    });

    // Stress Line Path
    const history = stressHistoryRef.current;
    const stepX = w / (history.length - 1);

    ctx.beginPath();
    ctx.lineWidth = 2.5;

    for (let i = 0; i < history.length; i++) {
      const val = history[i];
      const x = i * stepX;
      const y = h - (val / 100) * (h - 10) - 5;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    // Gradient fill under stress curve
    ctx.lineTo(w, h);
    ctx.lineTo(0, h);
    ctx.closePath();

    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, "rgba(244, 63, 94, 0.35)");
    grad.addColorStop(0.5, "rgba(245, 158, 11, 0.2)");
    grad.addColorStop(1, "rgba(16, 185, 129, 0.05)");
    ctx.fillStyle = grad;
    ctx.fill();

    // Re-stroke top line
    ctx.beginPath();
    for (let i = 0; i < history.length; i++) {
      const val = history[i];
      const x = i * stepX;
      const y = h - (val / 100) * (h - 10) - 5;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.strokeStyle = stressScore > 65 ? "#F43F5E" : stressScore > 40 ? "#F59E0B" : "#10B981";
    ctx.stroke();
  };

  // Commit Interrogation Transcript and Peak Stress to Database
  const handleCommitToCase = async () => {
    if (!transcriptLog.length && !liveTranscript) {
      alert("No interrogation audio transcript captured yet. Please speak into the mic before saving.");
      return;
    }

    setIsCommitting(true);
    cyberAudio?.playClick?.();

    const fullText = transcriptLog.map((t) => t.text).join(" ") + (liveTranscript ? " " + liveTranscript : "");

    try {
      await api("/nlp/ingest", {
        method: "POST",
        body: {
          case_id: caseRef,
          subject_name: interrogateSubject,
          subject_role: "SUSPECT",
          statement_title: `Live Audio Interrogation - Peak Stress ${peakStress}%`,
          interviewer_name: "Detective Voice Analysis Sensor",
          transcript_text: fullText.trim(),
        },
      });

      cyberAudio?.playSuccess?.();
      alert(`Interrogation session saved to ${caseRef}! Peak Stress: ${peakStress}%. Full CBCA veracity report generated.`);
      onLogToCase?.();
      stopAudioInterrogation();
      onClose?.();
    } catch (err) {
      console.error("Failed to commit statement", err);
      alert("Error saving interrogation statement. Check server connection.");
    } finally {
      setIsCommitting(false);
    }
  };

  return (
    <Card className="p-5 border-2 border-cyan/40 bg-slate-900/95 shadow-2xl relative">
      {/* Top Header & Close */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle pb-3 mb-4">
        <div className="flex items-center gap-2.5">
          <span className="text-xl animate-pulse">🎙️</span>
          <div>
            <h2 className="text-lg font-bold text-white tracking-wider uppercase flex items-center gap-2">
              Real-Time Voice Stress & Pitch Tremor Monitor
              <Badge tone={isActive ? "red" : "gray"}>
                {isActive ? "LIVE TELEMETRY SENSOR" : "STANDBY"}
              </Badge>
            </h2>
            <p className="text-[11px] font-mono text-muted">
              Computer Voice Stress Analysis (CVSA) · Autocorrelation Pitch $F_0$ · Micro-Tremor Jitter % · Hesitation Gaps
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {!isActive ? (
            <button
              onClick={startAudioInterrogation}
              className="btn btn-primary bg-cyan hover:bg-cyan-light text-black font-mono text-xs px-4 py-2 font-bold shadow-lg"
            >
              ▶ START LIVE AUDIO INTERROGATION
            </button>
          ) : (
            <button
              onClick={stopAudioInterrogation}
              className="btn btn-outline border-rose-500 text-rose-400 hover:bg-rose-500 hover:text-white font-mono text-xs px-3 py-2"
            >
              ⏹ STOP SENSOR
            </button>
          )}

          {onClose && (
            <button
              onClick={() => {
                stopAudioInterrogation();
                onClose();
              }}
              className="p-1.5 text-muted hover:text-white rounded"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {permissionError && (
        <div className="p-3 mb-4 rounded bg-rose-950/40 border border-rose-500/50 text-rose-300 font-mono text-xs">
          ⚠️ {permissionError}
        </div>
      )}

      {/* 4 Stat KPI Metric Boxes */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <StatBox
          label="VOICE STRESS LEVEL"
          value={`${stressScore}%`}
          caption={stressLevel}
          accent={stressScore > 65 ? "magenta" : stressScore > 40 ? "gold" : "emerald"}
        />
        <StatBox
          label="PITCH FREQUENCY (F0)"
          value={currentPitch > 0 ? `${currentPitch} Hz` : "--"}
          caption="Fundamental Vocal Pitch"
          accent="cyan"
        />
        <StatBox
          label="VOCAL JITTER (TREMOR)"
          value={`${currentJitter}%`}
          caption={currentJitter > 2.0 ? "UNNATURAL STRAIN" : "NORMAL VOCAL STABILITY"}
          accent={currentJitter > 2.0 ? "gold" : "cyan"}
        />
        <StatBox
          label="AUDIO AMPLITUDE (RMS)"
          value={`${currentDecibels} dB`}
          caption="Signal Strength"
          accent="emerald"
        />
      </div>

      {/* Main Dual-Canvas Telemetry Deck */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Left: Oscilloscope Spectrum */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-cyan font-bold">VOCAL SPECTRUM & OSCILLOSCOPE WAVEFORM</span>
            <span className="text-muted">FFT 2048 BINS</span>
          </div>
          <canvas
            ref={waveformCanvasRef}
            width={520}
            height={160}
            className="w-full h-40 rounded bg-[#070b14] border border-cyan/30 shadow-inner"
          />
          <span className="text-[10px] font-mono text-muted block">
            Green = Normal Vocal Cord Vibration | Red = High Micro-Tremor Distortion
          </span>
        </div>

        {/* Right: Scrolling Stress Graph */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-mono">
            <span className="text-gold font-bold">REAL-TIME STRESS TELEMETRY TIMELINE</span>
            <span className="text-rose-400 font-bold">PEAK STRESS: {peakStress}%</span>
          </div>
          <canvas
            ref={stressCanvasRef}
            width={520}
            height={160}
            className="w-full h-40 rounded bg-[#070b14] border border-gold/30 shadow-inner"
          />
          <div className="flex justify-between text-[10px] font-mono text-muted">
            <span>&lt; 35% Baseline Calm</span>
            <span className="text-gold">35-65% Cognitive Hesitation</span>
            <span className="text-rose-400 font-bold">&gt; 65% Deception Indicator</span>
          </div>
        </div>
      </div>

      {/* Live Interrogation Speech Transcript & Action Deck */}
      <div className="space-y-3 border-t border-border-subtle pt-3">
        <div className="flex items-center justify-between text-xs font-mono">
          <span className="text-white font-bold flex items-center gap-2">
            <span>📝</span> LIVE SPEECH TRANSCRIPTION LOG
          </span>
          <div className="flex items-center gap-2">
            <span className="text-muted">SUBJECT:</span>
            <input
              type="text"
              value={interrogateSubject}
              onChange={(e) => setInterrogateSubject(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white rounded px-2 py-0.5 text-xs w-36"
              placeholder="Suspect Name"
            />
          </div>
        </div>

        {/* Running Transcript Box */}
        <div className="h-32 overflow-y-auto p-3 rounded bg-slate-950/70 border border-slate-800 font-mono text-xs space-y-1.5">
          {transcriptLog.length === 0 && !liveTranscript ? (
            <div className="text-muted italic text-center pt-8">
              {isActive
                ? "Listening... Speak clearly into your laptop microphone to test live stress telemetry."
                : "Sensor is on standby. Click 'START LIVE AUDIO INTERROGATION' above."}
            </div>
          ) : (
            <>
              {transcriptLog.map((item, idx) => (
                <div key={idx} className="flex items-start justify-between gap-2 p-1.5 rounded bg-slate-900/60">
                  <div className="text-slate-200">
                    <span className="text-muted text-[10px] mr-2">[{item.timestamp}]</span>
                    {item.text}
                  </div>
                  <span
                    className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${
                      item.stress > 65
                        ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                        : item.stress > 40
                        ? "bg-amber-500/20 text-amber-300"
                        : "bg-emerald-500/20 text-emerald-400"
                    }`}
                  >
                    {item.stress}% STRESS
                  </span>
                </div>
              ))}
              {liveTranscript && (
                <div className="text-cyan animate-pulse">
                  <span className="text-muted text-[10px] mr-2">[TRANSCRIBING...]</span>
                  {liveTranscript}
                </div>
              )}
            </>
          )}
        </div>

        {/* Bottom Commit Action Button */}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <div className="text-[11px] font-mono text-muted">
            <span>Hesitations: <b>{hesitationCount}</b></span>
            <span className="mx-2">·</span>
            <span>Audio Codec: <b>Web Audio PCM 32-bit Float</b></span>
          </div>

          <button
            onClick={handleCommitToCase}
            disabled={isCommitting || (!transcriptLog.length && !liveTranscript)}
            className="btn btn-primary bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs px-4 py-2 font-bold shadow-md disabled:opacity-40"
          >
            {isCommitting ? "⏳ INGESTING STATEMENT..." : "💾 COMMIT INTERROGATION AS EVIDENCE TO CASE"}
          </button>
        </div>
      </div>
    </Card>
  );
}
