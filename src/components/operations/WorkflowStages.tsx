"use client";

import { useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { tradeWorkflow } from "@/data/operations";
import { cn } from "@/lib/utils";
import { EASE } from "@/components/site/primitives";

export function WorkflowStages() {
  const [active, setActive] = useState(0);
  const reduce = useReducedMotion();
  const stage = tradeWorkflow[active];

  return (
    <div className="grid gap-10 lg:grid-cols-12">
      <div role="tablist" aria-label="Trade workflow stages" className="flex flex-col lg:col-span-5">
        {tradeWorkflow.map((s, i) => (
          <button
            key={s.step}
            role="tab"
            id={`wf-tab-${i}`}
            aria-selected={active === i}
            aria-controls="wf-panel"
            onClick={() => setActive(i)}
            className={cn(
              "group relative flex cursor-pointer items-baseline gap-6 border-b border-line py-6 text-left transition-colors",
              active === i ? "text-ink" : "text-ink-subtle hover:text-ink"
            )}
          >
            <span className="font-mono text-xs text-brand">{s.step}</span>
            <span className="eb-display text-[clamp(1.6rem,2.6vw,2.3rem)]">{s.title}</span>
            {active === i && (
              <motion.span layoutId="wf-indicator" className="absolute -bottom-px left-0 h-px w-full bg-brand" transition={{ duration: reduce ? 0 : 0.5, ease: EASE }} />
            )}
          </button>
        ))}
      </div>
      <div className="lg:col-span-7">
        <AnimatePresence mode="wait">
          <motion.div
            key={stage.step}
            id="wf-panel"
            role="tabpanel"
            aria-labelledby={`wf-tab-${active}`}
            className="eb-frame h-full p-8 sm:p-12"
            initial={{ opacity: 0, y: reduce ? 0 : 14 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, transition: { duration: 0.18 } }}
            transition={{ duration: 0.5, ease: EASE }}
          >
            <p className="eb-eyebrow">Stage {stage.step} / 04</p>
            <p className="mt-6 text-lg leading-relaxed text-ink sm:text-xl">{stage.description}</p>
            <ul className="mt-10 space-y-4">
              {stage.points.map((p) => (
                <li key={p} className="flex gap-4 text-ink-muted">
                  <span className="mt-3 h-px w-5 shrink-0 bg-brand" aria-hidden="true" />
                  {p}
                </li>
              ))}
            </ul>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}
