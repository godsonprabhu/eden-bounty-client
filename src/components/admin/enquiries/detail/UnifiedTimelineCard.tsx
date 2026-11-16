"use client";

import React, { useState } from "react";
import {
  ArrowDownUp,
  Clock,
  FileCheck2,
  GitCommit,
  MessageSquare,
  RefreshCw,
  UserCheck,
} from "lucide-react";
import { EnquiryDetailResponseData, EnquiryTimelineEvent, TimelineEventType } from "@/types/admin";
import { synthesizeEnquiryTimeline, TimelineSortOrder } from "./timeline-utils";

interface UnifiedTimelineCardProps {
  dossier: EnquiryDetailResponseData;
}

export function UnifiedTimelineCard({ dossier }: UnifiedTimelineCardProps) {
  const [sortOrder, setSortOrder] = useState<TimelineSortOrder>("desc");

  const timelineEvents = synthesizeEnquiryTimeline(dossier, sortOrder);

  const toggleSortOrder = () => {
    setSortOrder((prev) => (prev === "desc" ? "asc" : "desc"));
  };

  return (
    <div className="rounded-[2px] border border-line eb-glass p-5 sm:p-6 shadow-2xs space-y-5">
      {/* Header & Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3.5 border-b border-line">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-[2px] bg-brand-soft flex items-center justify-center border border-brand/40">
            <Clock className="h-3.5 w-3.5 text-brand" />
          </div>
          <div>
            <h2 className="text-xs font-heading font-bold uppercase tracking-wider text-ink">
              Chronological Operational Timeline
            </h2>
            <p className="text-[11px] font-mono text-ink-subtle">
              Immutable audit history of commercial actions & transitions
            </p>
          </div>
        </div>

        {/* Sort Order Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-mono text-ink-subtle">
            Order:
          </span>
          <button
            type="button"
            onClick={toggleSortOrder}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[2px] border border-line bg-panel-2 text-xs font-mono font-medium text-ink hover:border-line-strong transition-colors cursor-pointer"
            title={`Current: ${sortOrder === "desc" ? "Newest first" : "Oldest first"}. Click to toggle.`}
          >
            <ArrowDownUp className="h-3 w-3 text-brand" />
            <span>{sortOrder === "desc" ? "Newest First" : "Oldest First"}</span>
          </button>
        </div>
      </div>

      {/* Events Stream */}
      {timelineEvents.length === 0 ? (
        <div className="text-center py-8 text-xs font-mono text-ink-subtle">
          No operational timeline events recorded.
        </div>
      ) : (
        <div className="relative pl-6 sm:pl-8 space-y-6 before:content-[''] before:absolute before:left-3 sm:before:left-4 before:top-2 before:bottom-2 before:w-[1px] before:bg-line">
          {timelineEvents.map((evt) => (
            <TimelineItem key={evt.eventId} event={evt} />
          ))}
        </div>
      )}
    </div>
  );
}

function TimelineItem({ event }: { event: EnquiryTimelineEvent }) {
  const badgeConfig = getEventTypeBadge(event.eventType);

  const formattedUtc = new Date(event.timestamp)
    .toISOString()
    .replace("T", " ")
    .replace(/\.\d{3}Z$/, " UTC");

  return (
    <div className="relative group">
      {/* Node Dot / Icon */}
      <div
        className={`absolute -left-6 sm:-left-8 top-0.5 h-6 w-6 rounded-full flex items-center justify-center border shadow-2xs ${badgeConfig.bg} ${badgeConfig.border} ${badgeConfig.text}`}
      >
        {badgeConfig.icon}
      </div>

      {/* Content Container */}
      <div className="space-y-1.5">
        {/* Title, Badge & UTC Timestamp */}
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-heading font-semibold text-xs text-ink">
              {event.title}
            </span>
            <span
              className={`inline-flex items-center px-1.5 py-0.2 rounded-[2px] text-[10px] font-mono font-medium border ${badgeConfig.bg} ${badgeConfig.border} ${badgeConfig.text}`}
            >
              {badgeConfig.label}
            </span>
          </div>

          <div className="flex items-center gap-1.5 text-[11px] font-mono text-ink-subtle">
            <Clock className="h-3 w-3 text-ink-subtle" />
            <span>{formattedUtc}</span>
          </div>
        </div>

        {/* Actor Info */}
        <div className="flex items-center gap-2 text-[11px] font-mono text-ink-subtle">
          <span>Initiator:</span>
          <span className="font-medium text-ink">
            {event.actorName}
          </span>
          {event.actorEmail && (
            <span className="text-ink-subtle">({event.actorEmail})</span>
          )}
        </div>

        {/* Description / Rationale */}
        {event.description && (
          <div className="p-3 rounded-[2px] bg-panel-2 border border-line text-xs font-mono text-ink-muted whitespace-pre-wrap leading-relaxed">
            {event.description}
          </div>
        )}
      </div>
    </div>
  );
}

function getEventTypeBadge(type: TimelineEventType): {
  label: string;
  bg: string;
  border: string;
  text: string;
  icon: React.ReactNode;
} {
  switch (type) {
    case "SUBMISSION":
      return {
        label: "Intake",
        bg: "bg-[#EFF6FF] dark:bg-[#112240]",
        border: "border-[#BFDBFE] dark:border-[#1E3A8A]",
        text: "text-[#1D4ED8] dark:text-[#60A5FA]",
        icon: <FileCheck2 className="h-3 w-3" />,
      };
    case "STATUS_CHANGE":
      return {
        label: "Transition",
        bg: "bg-[#FFFBEB] dark:bg-[#2D2312]",
        border: "border-[#FDE68A] dark:border-[#78350F]",
        text: "text-[#B45309] dark:text-[#FBBF24]",
        icon: <RefreshCw className="h-3 w-3" />,
      };
    case "ASSIGNMENT":
      return {
        label: "Assignment",
        bg: "bg-[#F5F3FF] dark:bg-[#241442]",
        border: "border-[#DDD6FE] dark:border-[#4C1D95]",
        text: "text-[#6D28D9] dark:text-[#C4B5FD]",
        icon: <UserCheck className="h-3 w-3" />,
      };
    case "NOTE":
      return {
        label: "Internal Note",
        bg: "bg-panel-2 ",
        border: "border-line-strong ",
        text: "text-ink-muted ",
        icon: <MessageSquare className="h-3 w-3" />,
      };
    default:
      return {
        label: "Event",
        bg: "bg-panel-2 ",
        border: "border-line ",
        text: "text-ink-subtle ",
        icon: <GitCommit className="h-3 w-3" />,
      };
  }
}
