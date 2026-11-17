import React, { useRef, useState } from "react";
import { cyberAudio } from "../utils/cyberAudio.js";

/**
 * Multi-Plane Holographic Parallax 3D Card
 * Child elements float on independent Z-planes creating authentic physical depth.
 */
export function TiltCard({ title, aside, children, className = "", onClick, style = {} }) {
  const cardRef = useRef(null);
  const [transform, setTransform] = useState("");
  const [isHovered, setIsHovered] = useState(false);

  const handlePointerMove = (e) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const centerX = rect.width / 2;
    const centerY = rect.height / 2;

    const rotateX = ((y - centerY) / centerY) * -6.5;
    const rotateY = ((x - centerX) / centerX) * 6.5;

    setTransform(`perspective(950px) rotateX(${rotateX.toFixed(2)}deg) rotateY(${rotateY.toFixed(2)}deg) translateZ(8px)`);

    cardRef.current.style.setProperty("--card-mouse-x", `${x}px`);
    cardRef.current.style.setProperty("--card-mouse-y", `${y}px`);
  };

  const handlePointerEnter = () => {
    setIsHovered(true);
    cyberAudio.playHoverBlip();
  };

  const handlePointerLeave = () => {
    setIsHovered(false);
    setTransform("perspective(950px) rotateX(0deg) rotateY(0deg) translateZ(0px)");
    if (cardRef.current) {
      cardRef.current.style.setProperty("--card-mouse-x", `-999px`);
      cardRef.current.style.setProperty("--card-mouse-y", `-999px`);
    }
  };

  return (
    <section
      ref={cardRef}
      className={`card cm-tilt-card cm-holographic-3d ${isHovered ? "is-hovered" : ""} ${className}`}
      style={{
        transform,
        transition: isHovered ? "transform 0.08s ease-out" : "transform 0.5s cubic-bezier(0.2, 0.8, 0.2, 1)",
        ...style,
      }}
      onPointerMove={handlePointerMove}
      onPointerEnter={handlePointerEnter}
      onPointerLeave={handlePointerLeave}
      onClick={onClick}
    >
      {/* Specular Light Reflection */}
      <div className="cm-card-specular" />
      {/* Holographic Glowing Edge */}
      <div className="cm-card-glow-border" />

      {/* Floating Z-Plane 1: Header (Z = 24px) */}
      {(title || aside) && (
        <header className="cm-z-plane-header">
          <div className="cm-card-title-wrap">
            <span className="cm-card-icon cm-z-plane-icon">◈</span>
            <h3>{title}</h3>
          </div>
          <div className="cm-z-plane-aside">{aside}</div>
        </header>
      )}

      {/* Floating Z-Plane 2: Content (Z = 12px) */}
      <div className="cm-card-content cm-z-plane-body">{children}</div>
    </section>
  );
}
