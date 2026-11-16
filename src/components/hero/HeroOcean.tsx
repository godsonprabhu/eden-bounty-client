"use client";

import { useEffect, useRef, useState } from "react";
import { useTheme } from "@/context/ThemeContext";
import type { ShipScene } from "./ShipScene";

function supportsWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/**
 * Full-bleed animated ocean with a container vessel under way.
 * Three.js is code-split and only loaded on the client; a static
 * CSS/SVG composition covers SSR, no-WebGL and context-loss cases.
 */
export function HeroOcean() {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sceneRef = useRef<ShipScene | null>(null);
  const { theme } = useTheme();
  const themeRef = useRef(theme);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    themeRef.current = theme;
    sceneRef.current?.setTheme(theme);
  }, [theme]);

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    if (!supportsWebGL()) {
      const id = requestAnimationFrame(() => setFailed(true));
      return () => cancelAnimationFrame(id);
    }
    let cancelled = false;
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const lowPower =
      window.matchMedia("(max-width: 767px)").matches ||
      (navigator.hardwareConcurrency ?? 8) <= 4;

    const onMotion = () => sceneRef.current?.setReducedMotion(motionQuery.matches);
    const onLost = (e: Event) => {
      e.preventDefault();
      setFailed(true);
    };
    canvas.addEventListener("webglcontextlost", onLost);

    import("./ShipScene")
      .then(({ ShipScene }) => {
        if (cancelled) return;
        sceneRef.current = new ShipScene({
          canvas,
          container,
          theme: themeRef.current,
          reducedMotion: motionQuery.matches,
          lowPower,
        });
        motionQuery.addEventListener("change", onMotion);
        requestAnimationFrame(() => !cancelled && setReady(true));
      })
      .catch(() => !cancelled && setFailed(true));

    return () => {
      cancelled = true;
      motionQuery.removeEventListener("change", onMotion);
      canvas.removeEventListener("webglcontextlost", onLost);
      sceneRef.current?.dispose();
      sceneRef.current = null;
    };
  }, []);

  return (
    <div ref={containerRef} className="absolute inset-0 overflow-hidden" aria-hidden="true">
      <OceanFallback />
      {!failed && (
        <canvas
          ref={canvasRef}
          className="absolute inset-0 h-full w-full transition-opacity duration-[1400ms] ease-out"
          style={{ opacity: ready ? 1 : 0 }}
        />
      )}
    </div>
  );
}

/** Static composition used before WebGL is ready or when it is unavailable. */
function OceanFallback() {
  return (
    <div className="absolute inset-0 bg-[radial-gradient(120%_90%_at_70%_45%,#2a93c2_0%,#14699a_50%,#0b4c74_100%)] dark:bg-[radial-gradient(120%_90%_at_70%_45%,#0d2a3a_0%,#06121b_45%,#02060a_100%)]">
      <svg
        className="absolute left-[58%] top-1/2 w-[min(62vw,820px)] -translate-x-1/2 -translate-y-1/2 -rotate-[28deg] opacity-90 max-md:left-1/2 max-md:top-[68%] max-md:w-[92vw]"
        viewBox="0 0 400 70"
      >
        <defs>
          <linearGradient id="eb-wake" x1="1" x2="0">
            <stop offset="0" stopColor="#fff" stopOpacity="0.55" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d="M60 35 L-200 0 L-200 70 Z" fill="url(#eb-wake)" opacity="0.35" />
        <path d="M58 22 H300 Q372 24 392 35 Q372 46 300 48 H58 Q52 35 58 22Z" fill="#151b22" stroke="#e6e9ec" strokeOpacity="0.5" />
        {Array.from({ length: 18 }).map((_, i) => (
          <rect
            key={i}
            x={96 + i * 11.4}
            y={25}
            width={10.4}
            height={20}
            fill={["#8a2e24", "#1d4b69", "#6c777d", "#2c6a70", "#ad7029", "#c6c0b0"][i % 6]}
            opacity="0.9"
          />
        ))}
        <rect x="70" y="21" width="16" height="28" fill="#e7e4dc" />
      </svg>
    </div>
  );
}
