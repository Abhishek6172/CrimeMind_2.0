import React, { useEffect, useRef, useState } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";

export function MouseEffects() {
  const canvasRef = useRef(null);
  const cursorRef = useRef(null);
  const trailRef = useRef(null);
  const reticleRef = useRef(null);
  const rippleContainerRef = useRef(null);

  const [coords, setCoords] = useState({ x: 0, y: 0, angle: 0 });

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReducedMotion) return;

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight / 2;
    let currentX = targetX;
    let currentY = targetY;
    let trailX = targetX;
    let trailY = targetY;
    let animId = null;

    const centerX = window.innerWidth / 2;
    const centerY = window.innerHeight / 2;

    const handlePointerMove = (e) => {
      targetX = e.clientX;
      targetY = e.clientY;

      document.documentElement.style.setProperty("--cursor-x", `${targetX}px`);
      document.documentElement.style.setProperty("--cursor-y", `${targetY}px`);

      // Calculate angle relative to screen center
      const rad = Math.atan2(targetY - centerY, targetX - centerX);
      const deg = Math.round((rad * 180) / Math.PI + 180);

      // Throttled UI state update for reticle telemetry
      if (Math.random() > 0.4) {
        setCoords({ x: Math.round(targetX), y: Math.round(targetY), angle: deg });
      }
    };

    const handlePointerDown = (e) => {
      cyberAudio.playClickChirp();

      if (!rippleContainerRef.current) return;
      const ripple = document.createElement("div");
      ripple.className = "cm-click-ripple";
      ripple.style.left = `${e.clientX}px`;
      ripple.style.top = `${e.clientY}px`;
      rippleContainerRef.current.appendChild(ripple);
      setTimeout(() => ripple.remove(), 700);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    window.addEventListener("pointerdown", handlePointerDown, { passive: true });

    // Cursor Follow & Trailing Loop
    const renderCursor = () => {
      currentX += (targetX - currentX) * 0.35;
      currentY += (targetY - currentY) * 0.35;
      trailX += (targetX - trailX) * 0.12;
      trailY += (targetY - trailY) * 0.12;

      if (cursorRef.current) {
        cursorRef.current.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
      }
      if (trailRef.current) {
        trailRef.current.style.transform = `translate3d(${trailX}px, ${trailY}px, 0)`;
      }
      if (reticleRef.current) {
        reticleRef.current.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
      }

      animId = requestAnimationFrame(renderCursor);
    };
    animId = requestAnimationFrame(renderCursor);

    // Canvas Matrix Hex Waterfall & Dynamic Tethering
    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      let width = (canvas.width = window.innerWidth);
      let height = (canvas.height = window.innerHeight);

      const handleResize = () => {
        if (!canvas) return;
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
      };
      window.addEventListener("resize", handleResize);

      // Hex data waterfall streams
      const hexChars = "0123456789ABCDEF•◈⌖EVLM_SHA256_Q40_CCTV";
      const columns = Math.floor(width / 34);
      const drops = Array(columns).fill(0).map(() => Math.floor(Math.random() * -100));

      // Cyber particles
      const particleCount = Math.min(Math.floor((width * height) / 24000), 45);
      const particles = [];
      for (let i = 0; i < particleCount; i++) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          vx: (Math.random() - 0.5) * 0.4,
          vy: (Math.random() - 0.5) * 0.4,
          radius: Math.random() * 1.8 + 0.8,
          color: Math.random() > 0.45 ? "rgba(0, 229, 255, " : "rgba(255, 181, 46, ",
          alpha: Math.random() * 0.35 + 0.1,
        });
      }

      let pAnimId = null;
      let frame = 0;

      const animateCanvas = () => {
        ctx.clearRect(0, 0, width, height);
        frame++;

        // 1. Matrix Hex Data Stream (Slow, subtle ambient background)
        if (frame % 2 === 0) {
          ctx.font = "9px 'JetBrains Mono', monospace";
          for (let i = 0; i < drops.length; i++) {
            const char = hexChars[Math.floor(Math.random() * hexChars.length)];
            const x = i * 34;
            const y = drops[i] * 18;

            if (y > 0) {
              const distToMouse = Math.hypot(targetX - x, targetY - y);
              // Scatter or glow when cursor sweeps near
              if (distToMouse < 90) {
                ctx.fillStyle = "rgba(255, 181, 46, 0.45)";
              } else {
                ctx.fillStyle = "rgba(0, 229, 255, 0.08)";
              }
              ctx.fillText(char, x, y);
            }

            if (y > height && Math.random() > 0.985) {
              drops[i] = 0;
            }
            drops[i]++;
          }
        }

        // 2. Cyber Particles & Proximity Lines
        for (let i = 0; i < particles.length; i++) {
          const p = particles[i];
          p.x += p.vx;
          p.y += p.vy;

          if (p.x < 0) p.x = width;
          else if (p.x > width) p.x = 0;
          if (p.y < 0) p.y = height;
          else if (p.y > height) p.y = 0;

          const dx = targetX - p.x;
          const dy = targetY - p.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 130) {
            const force = (130 - dist) / 130;
            p.x -= (dx / dist) * force * 1.1;
            p.y -= (dy / dist) * force * 1.1;
          }

          ctx.beginPath();
          ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
          ctx.fillStyle = `${p.color}${p.alpha})`;
          ctx.fill();

          for (let j = i + 1; j < particles.length; j++) {
            const p2 = particles[j];
            const d = Math.hypot(p.x - p2.x, p.y - p2.y);
            if (d < 100) {
              const lineAlpha = (1 - d / 100) * 0.15;
              ctx.beginPath();
              ctx.moveTo(p.x, p.y);
              ctx.lineTo(p2.x, p2.y);
              ctx.strokeStyle = `rgba(0, 229, 255, ${lineAlpha})`;
              ctx.lineWidth = 0.7;
              ctx.stroke();
            }
          }

          // Magnetic tether line to cursor
          if (dist < 150) {
            const mouseAlpha = (1 - dist / 150) * 0.35;
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(targetX, targetY);
            ctx.strokeStyle = `rgba(255, 181, 46, ${mouseAlpha})`;
            ctx.lineWidth = 0.85;
            ctx.stroke();
          }
        }

        pAnimId = requestAnimationFrame(animateCanvas);
      };
      pAnimId = requestAnimationFrame(animateCanvas);

      return () => {
        window.removeEventListener("pointermove", handlePointerMove);
        window.removeEventListener("pointerdown", handlePointerDown);
        window.removeEventListener("resize", handleResize);
        if (animId) cancelAnimationFrame(animId);
        if (pAnimId) cancelAnimationFrame(pAnimId);
      };
    }

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerdown", handlePointerDown);
      if (animId) cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <div className="cm-interactive-layer" aria-hidden="true">
      {/* Background Matrix & Particle Canvas */}
      <canvas ref={canvasRef} className="cm-particle-canvas" />

      {/* Global Cursor Spotlight */}
      <div className="cm-spotlight" />

      {/* Trailing Holographic Halo */}
      <div ref={trailRef} className="cm-cursor-trail" />

      {/* Dual-Tone Precision Crosshair Dot */}
      <div ref={cursorRef} className="cm-cursor-dot" />

      {/* Real-Time HUD Target Reticle with Telemetry Coordinates */}
      <div ref={reticleRef} className="cm-hud-reticle">
        <div className="cm-reticle-crosshair" />
        <div className="cm-reticle-telemetry font-mono">
          <span>X:{String(coords.x).padStart(4, "0")} Y:{String(coords.y).padStart(4, "0")}</span>
          <span>θ:{String(coords.angle).padStart(3, "0")}° 60FPS</span>
        </div>
      </div>

      {/* Click Ripple Container */}
      <div ref={rippleContainerRef} className="cm-ripple-container" />
    </div>
  );
}
