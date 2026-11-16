"use client";

import React from "react";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";
import { useGlobalUIState, ToastMessage, ToastType } from "@/context/GlobalUIStateContext";

const TOAST_ICONS: Record<ToastType, React.ComponentType<{ className?: string }>> = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

const TOAST_STYLES: Record<
  ToastType,
  {
    border: string;
    bg: string;
    iconColor: string;
    titleColor: string;
    textColor: string;
  }
> = {
  success: {
    border: "border-[#059669]/40 dark:border-[#10B981]/40",
    bg: "bg-[#F0FDF4] dark:bg-[#071F14]",
    iconColor: "text-[#059669] dark:text-[#10B981]",
    titleColor: "text-[#065F46] dark:text-[#34D399]",
    textColor: "text-[#14532D] dark:text-[#A7F3D0]",
  },
  error: {
    border: "border-[#DC2626]/40 dark:border-[#EF4444]/40",
    bg: "bg-[#FEF2F2] dark:bg-[#200A0D]",
    iconColor: "text-[#DC2626] dark:text-[#EF4444]",
    titleColor: "text-[#991B1B] dark:text-[#F87171]",
    textColor: "text-[#7F1D1D] dark:text-[#FCA5A5]",
  },
  warning: {
    border: "border-[#D97706]/40 dark:border-[#F59E0B]/40",
    bg: "bg-[#FFFBEB] dark:bg-[#201503]",
    iconColor: "text-[#D97706] dark:text-[#F59E0B]",
    titleColor: "text-[#92400E] dark:text-[#FBBF24]",
    textColor: "text-[#78350F] dark:text-[#FDE68A]",
  },
  info: {
    border: "border-brand/40 ",
    bg: "bg-brand-soft dark:bg-[#041624]",
    iconColor: "text-brand ",
    titleColor: "text-[#075985] ",
    textColor: "text-[#0C4A6E] dark:text-[#BAE6FD]",
  },
};

function ToastItem({
  toast,
  onDismiss,
}: {
  toast: ToastMessage;
  onDismiss: (id: string) => void;
}) {
  const Icon = TOAST_ICONS[toast.type];
  const style = TOAST_STYLES[toast.type];

  return (
    <div
      role={toast.type === "error" ? "alert" : "status"}
      aria-live={toast.type === "error" ? "assertive" : "polite"}
      className={`pointer-events-auto w-full max-w-sm rounded-[2px] border ${style.border} ${style.bg} p-3.5 shadow-xl transition-all duration-200 animate-in slide-in-from-top-2 sm:slide-in-from-right-4 fade-in`}
    >
      <div className="flex items-start gap-3">
        <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-[2px] ${style.iconColor}`}>
          <Icon className="h-4 w-4" />
        </span>
        <div className="flex-1 min-w-0 space-y-0.5">
          {toast.title && (
            <h4 className={`font-heading text-xs font-bold uppercase tracking-wider ${style.titleColor}`}>
              {toast.title}
            </h4>
          )}
          <p className={`font-body text-xs ${style.textColor} leading-snug break-words`}>
            {toast.message}
          </p>
        </div>
        <button
          type="button"
          onClick={() => onDismiss(toast.id)}
          aria-label="Dismiss notification"
          className={`shrink-0 inline-flex min-h-[32px] min-w-[32px] items-center justify-center rounded-[2px] opacity-70 hover:opacity-100 ${style.iconColor} transition-opacity cursor-pointer`}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

export function ToastContainer() {
  const { toasts, removeToast } = useGlobalUIState();

  if (toasts.length === 0) {
    return null;
  }

  return (
    <aside
      aria-label="Notifications"
      className="fixed top-4 right-4 z-[150] pointer-events-none flex flex-col gap-2.5 max-w-sm w-full px-4 sm:px-0"
    >
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onDismiss={removeToast} />
      ))}
    </aside>
  );
}
