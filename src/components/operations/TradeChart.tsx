"use client";

import { motion, useReducedMotion } from "motion/react";
import { divisionClusters } from "@/data/operations";

const CX = 500;
const CY = 300;
const BEARINGS = [-38, 28, 152, 212]; // purely illustrative headings per division cluster

/**
 * Illustrative nautical-style chart centred on the Shah Alam head office.
 * Bearings represent the four division clusters handled by the commercial desk —
 * not published shipping routes.
 */
export function TradeChart() {
  const reduce = useReducedMotion();
  return (
    <figure className="eb-frame relative overflow-hidden">
      <svg viewBox="0 0 1000 600" className="block h-auto w-full" role="img" aria-labelledby="chart-title chart-desc">
        <title id="chart-title">Commercial desk chart</title>
        <desc id="chart-desc">
          Head office in Shah Alam, Selangor at the centre, with four bearings representing the Energy, Industrial, Consumer and
          Drone service clusters.
        </desc>
        {/* graticule */}
        <g stroke="var(--eb-line)" strokeWidth="1">
          {Array.from({ length: 11 }).map((_, i) => (
            <line key={`v${i}`} x1={i * 100} y1="0" x2={i * 100} y2="600" />
          ))}
          {Array.from({ length: 7 }).map((_, i) => (
            <line key={`h${i}`} x1="0" y1={i * 100} x2="1000" y2={i * 100} />
          ))}
        </g>
        <g fill="var(--eb-ink-subtle)" fontFamily="var(--font-mono)" fontSize="11" letterSpacing="2">
          <text x="508" y="18">101°31′E</text>
          <text x="8" y="296">03°04′N</text>
        </g>
        {/* range rings */}
        {[80, 160, 240].map((r, i) => (
          <motion.circle
            key={r}
            cx={CX}
            cy={CY}
            r={r}
            fill="none"
            stroke="var(--eb-line-strong)"
            strokeDasharray="2 6"
            initial={{ opacity: 0, scale: 0.9 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 1.2, delay: i * 0.15 }}
            style={{ transformOrigin: `${CX}px ${CY}px` }}
          />
        ))}
        {/* sonar pulse */}
        {!reduce && (
          <motion.circle
            cx={CX}
            cy={CY}
            r={260}
            fill="none"
            stroke="var(--eb-brand)"
            strokeWidth="1"
            initial={{ scale: 0.05, opacity: 0.7 }}
            animate={{ scale: 1, opacity: 0 }}
            transition={{ duration: 4.5, repeat: Infinity, ease: "easeOut" }}
            style={{ transformOrigin: `${CX}px ${CY}px` }}
          />
        )}
        {/* bearings */}
        {divisionClusters.map((c, i) => {
          const a = (BEARINGS[i] * Math.PI) / 180;
          const len = 250 + (i % 2) * 40;
          const x = CX + Math.cos(a) * len;
          const y = CY + Math.sin(a) * len * 0.82;
          const mx = CX + Math.cos(a - 0.35) * len * 0.55;
          const my = CY + Math.sin(a - 0.35) * len * 0.45;
          const d = `M${CX} ${CY} Q${mx} ${my} ${x} ${y}`;
          const anchor = x > CX ? "start" : "end";
          return (
            <g key={c.code}>
              <motion.path
                d={d}
                fill="none"
                stroke="var(--eb-brand)"
                strokeWidth="1.4"
                initial={{ pathLength: 0 }}
                whileInView={{ pathLength: 1 }}
                viewport={{ once: true }}
                transition={{ duration: reduce ? 0 : 1.6, delay: 0.4 + i * 0.2, ease: [0.22, 1, 0.36, 1] }}
              />
              <path d={d} fill="none" stroke="var(--eb-brand)" strokeOpacity="0.25" strokeWidth="6" />
              <circle cx={x} cy={y} r="4" fill="var(--eb-paper)" stroke="var(--eb-brand)" strokeWidth="1.5" />
              <text x={x + (anchor === "start" ? 12 : -12)} y={y - 6} textAnchor={anchor} fill="var(--eb-ink)" fontSize="15" fontFamily="var(--font-body)">
                {c.category}
              </text>
              <text x={x + (anchor === "start" ? 12 : -12)} y={y + 12} textAnchor={anchor} fill="var(--eb-ink-subtle)" fontSize="10" letterSpacing="1.5" fontFamily="var(--font-mono)">
                {c.code}
              </text>
            </g>
          );
        })}
        {/* head office */}
        <circle cx={CX} cy={CY} r="9" fill="var(--eb-brand)" />
        <circle cx={CX} cy={CY} r="16" fill="none" stroke="var(--eb-brand)" strokeOpacity="0.5" />
        <text x={CX} y={CY + 40} textAnchor="middle" fill="var(--eb-ink)" fontSize="13" letterSpacing="3" fontFamily="var(--font-mono)">
          SHAH ALAM · HQ
        </text>
        {/* compass */}
        <g transform="translate(920 90)" stroke="var(--eb-ink-subtle)" fill="none">
          <circle r="34" strokeOpacity="0.5" />
          <path d="M0 -44 L6 0 L0 44 L-6 0 Z" fill="var(--eb-ink-subtle)" fillOpacity="0.25" />
          <text y="-50" textAnchor="middle" fill="var(--eb-ink-subtle)" stroke="none" fontSize="11" fontFamily="var(--font-mono)">
            N
          </text>
        </g>
      </svg>
      <figcaption className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4 font-mono text-[0.64rem] uppercase tracking-[0.2em] text-ink-subtle">
        <span>Illustrative chart · not to scale</span>
        <span>Bearings denote service clusters, not fixed shipping lanes</span>
      </figcaption>
    </figure>
  );
}
