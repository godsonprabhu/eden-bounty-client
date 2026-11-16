"use client";

import React from "react";
import { WifiOff, Wifi, X, RefreshCw } from "lucide-react";
import { useGlobalUIState } from "@/context/GlobalUIStateContext";

export function GlobalOfflineBanner() {
  const { isOnline, reconnectedAt, dismissReconnectedBanner } = useGlobalUIState();

  // If online and no recent reconnection, render nothing
  if (isOnline && !reconnectedAt) {
    return null;
  }

  // 1. Connection Restored Notice (auto-dismissed or manually closed)
  if (isOnline && reconnectedAt) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="fixed top-0 inset-x-0 z-[100] border-b border-[#059669]/30 bg-[#ECFDF5] dark:bg-[#062419] px-4 py-2.5 text-xs text-[#065F46] dark:text-[#34D399] shadow-md transition-all duration-200"
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[2px] bg-[#10B981]/20 text-[#059669] dark:text-[#10B981]">
              <Wifi className="h-3.5 w-3.5" />
            </span>
            <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] sm:text-xs min-w-0">
              <span className="font-semibold uppercase tracking-wider text-[#047857] dark:text-[#10B981]">
                Connection Restored:
              </span>
              <span className="text-[#065F46] dark:text-[#A7F3D0] truncate">
                Internet connectivity has returned. Live operations resumed.
              </span>
            </div>
          </div>
          <button
            type="button"
            onClick={dismissReconnectedBanner}
            aria-label="Dismiss connection restored notification"
            className="inline-flex min-h-[32px] min-w-[32px] items-center justify-center rounded-[2px] text-[#065F46] hover:bg-[#D1FAE5] dark:text-[#A7F3D0] dark:hover:bg-[#0A3D2B] transition-colors cursor-pointer"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    );
  }

  // 2. Active Offline Status Banner
  return (
    <aside
      role="status"
      aria-live="polite"
      className="fixed top-0 inset-x-0 z-[100] border-b border-[#D97706]/40 bg-[#FFFBEB] dark:bg-[#1C1304] px-4 py-2.5 text-xs text-[#92400E] dark:text-[#FCD34D] shadow-md transition-all duration-200"
    >
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[2px] bg-[#F59E0B]/20 text-[#D97706] dark:text-[#F59E0B] animate-pulse">
            <WifiOff className="h-3.5 w-3.5" />
          </span>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 font-mono text-[11px] sm:text-xs min-w-0">
            <span className="font-semibold uppercase tracking-wider text-[#B45309] dark:text-[#F59E0B]">
              Offline Mode Detected:
            </span>
            <span className="text-[#78350F] dark:text-[#FDE68A] truncate">
              Internet connection lost. New submissions and data synchronization are paused.
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() => {
              if (typeof window !== "undefined") {
                window.location.reload();
              }
            }}
            className="inline-flex min-h-[32px] items-center gap-1 px-2.5 py-1 rounded-[2px] border border-[#F59E0B]/40 bg-panel dark:bg-[#2A1D07] font-mono text-[10px] uppercase tracking-wider text-[#92400E] dark:text-[#FCD34D] hover:bg-[#FEF3C7] dark:hover:bg-[#3D2908] transition-colors cursor-pointer"
          >
            <RefreshCw className="h-3 w-3" />
            <span className="hidden sm:inline">Retry Connection</span>
          </button>
        </div>
      </div>
    </aside>
  );
}
