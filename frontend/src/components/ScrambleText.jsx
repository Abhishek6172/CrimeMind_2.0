import React, { useEffect, useState, useRef } from "react";

const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?/~";

/**
 * High-tech Hacker Decryption Text Effect
 * Letters scramble through cryptographic symbols before locking into place.
 */
export function ScrambleText({ text = "", speed = 25, delay = 0, className = "" }) {
  const [display, setDisplay] = useState(text);
  const animRef = useRef(null);

  useEffect(() => {
    let iteration = 0;
    const target = String(text);
    const length = target.length;

    const timer = setTimeout(() => {
      animRef.current = setInterval(() => {
        setDisplay(
          target
            .split("")
            .map((char, index) => {
              if (index < iteration) {
                return target[index];
              }
              if (char === " " || char === "\n") return char;
              return CHARS[Math.floor(Math.random() * CHARS.length)];
            })
            .join("")
        );

        if (iteration >= length) {
          clearInterval(animRef.current);
        }
        iteration += 1 / 2;
      }, speed);
    }, delay);

    return () => {
      clearTimeout(timer);
      if (animRef.current) clearInterval(animRef.current);
    };
  }, [text, speed, delay]);

  return <span className={`cm-scramble-text ${className}`}>{display}</span>;
}
