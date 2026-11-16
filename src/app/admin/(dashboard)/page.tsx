"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useAdminAuth } from "@/context/AdminAuthContext";
import {
  apiGetDashboardOverview,
  apiGetRecentEnquiries,
  apiGetDashboardActivity,
  AdminApiError,
} from "@/lib/admin-api";
import {
  AdminOverviewMetrics,
  EnquiryListItem,
  DashboardActivityItem,
} from "@/types/admin";
import { DashboardOverviewHeader } from "@/components/admin/dashboard/DashboardOverviewHeader";
import { PortalSummaryCards } from "@/components/admin/portal/PortalSummaryCards";
import { OverviewMetricsGrid } from "@/components/admin/dashboard/OverviewMetricsGrid";
import { DivisionDistributionCard } from "@/components/admin/dashboard/DivisionDistributionCard";
import { RecentEnquiriesCard } from "@/components/admin/dashboard/RecentEnquiriesCard";
import { RecentActivityFeed } from "@/components/admin/dashboard/RecentActivityFeed";
import { DashboardSkeleton } from "@/components/admin/dashboard/DashboardSkeleton";
import { DashboardErrorState } from "@/components/admin/dashboard/DashboardErrorState";
import { StatePartialData } from "@/components/ui/states";
import { useToast } from "@/hooks/useToast";

async function fetchAllDashboardModules() {
  const [overviewRes, recentRes, activityRes] = await Promise.allSettled([
    apiGetDashboardOverview(),
    apiGetRecentEnquiries(5),
    apiGetDashboardActivity(10),
  ]);
  return { overviewRes, recentRes, activityRes };
}

export default function AdminDashboardOverviewPage() {
  const { user } = useAdminAuth();
  const { toast } = useToast();

  const [metrics, setMetrics] = useState<AdminOverviewMetrics | null>(null);
  const [recentEnquiries, setRecentEnquiries] = useState<EnquiryListItem[]>([]);
  const [activities, setActivities] = useState<DashboardActivityItem[]>([]);

  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [overviewError, setOverviewError] = useState<string | null>(null);
  const [activityError, setActivityError] = useState<string | null>(null);
  const [recentEnquiriesError, setRecentEnquiriesError] = useState<string | null>(null);
  const [isRetryingActivity, setIsRetryingActivity] = useState<boolean>(false);
  const [isRetryingRecent, setIsRetryingRecent] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  // Initial load on mount
  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      const { overviewRes, recentRes, activityRes } = await fetchAllDashboardModules();
      if (!isMounted) return;

      if (overviewRes.status === "fulfilled") {
        setMetrics(overviewRes.value);
        setOverviewError(null);
      } else {
        const err = overviewRes.reason;
        const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Failed to load overview metrics";
        setOverviewError(msg);
      }

      if (recentRes.status === "fulfilled") {
        setRecentEnquiries(recentRes.value);
        setRecentEnquiriesError(null);
      } else {
        const err = recentRes.reason;
        const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Recent enquiries could not be loaded";
        setRecentEnquiriesError(msg);
      }

      if (activityRes.status === "fulfilled") {
        setActivities(activityRes.value);
        setActivityError(null);
      } else {
        const err = activityRes.reason;
        const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Activity feed could not be loaded";
        setActivityError(msg);
      }

      setLastUpdated(new Date());
      setIsLoading(false);
    }

    loadData();

    return () => {
      isMounted = false;
    };
  }, []);

  // Global manual refresh
  const handleManualRefresh = useCallback(async () => {
    setIsRefreshing(true);
    const { overviewRes, recentRes, activityRes } = await fetchAllDashboardModules();

    if (overviewRes.status === "fulfilled") {
      setMetrics(overviewRes.value);
      setOverviewError(null);
    } else {
      const err = overviewRes.reason;
      const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Failed to load overview metrics";
      setOverviewError(msg);
    }

    if (recentRes.status === "fulfilled") {
      setRecentEnquiries(recentRes.value);
      setRecentEnquiriesError(null);
    } else {
      const err = recentRes.reason;
      const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Recent enquiries could not be loaded";
      setRecentEnquiriesError(msg);
    }

    if (activityRes.status === "fulfilled") {
      setActivities(activityRes.value);
      setActivityError(null);
    } else {
      const err = activityRes.reason;
      const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Activity feed could not be loaded";
      setActivityError(msg);
    }

    setLastUpdated(new Date());
    setIsRefreshing(false);
  }, []);

  // Isolated retry for Activity Feed module (no full page reload)
  const handleRetryActivity = useCallback(async () => {
    setIsRetryingActivity(true);
    try {
      const data = await apiGetDashboardActivity(10);
      setActivities(data);
      setActivityError(null);
      toast.success("Activity feed updated successfully.");
    } catch (err: unknown) {
      const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Failed to load activity feed";
      setActivityError(msg);
      toast.error("Unable to reload activity feed.");
    } finally {
      setIsRetryingActivity(false);
    }
  }, [toast]);

  // Isolated retry for Recent Enquiries module (no full page reload)
  const handleRetryRecent = useCallback(async () => {
    setIsRetryingRecent(true);
    try {
      const data = await apiGetRecentEnquiries(5);
      setRecentEnquiries(data);
      setRecentEnquiriesError(null);
      toast.success("Recent enquiries refreshed successfully.");
    } catch (err: unknown) {
      const msg = err instanceof AdminApiError ? err.detail : err instanceof Error ? err.message : "Failed to load recent enquiries";
      setRecentEnquiriesError(msg);
      toast.error("Unable to reload recent enquiries.");
    } finally {
      setIsRetryingRecent(false);
    }
  }, [toast]);

  // Initial full page loading state
  if (isLoading && !metrics) {
    return <DashboardSkeleton />;
  }

  // Critical failure: Overview metrics completely missing
  if (overviewError && !metrics) {
    return (
      <DashboardErrorState
        error={overviewError}
        onRetry={handleManualRefresh}
      />
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* 1. Header with greeting, UTC server indicator, quick counts, and refresh */}
      <DashboardOverviewHeader
        user={user}
        todayCount={metrics?.today_count || 0}
        unassignedCount={metrics?.unassigned_count || 0}
        onRefresh={handleManualRefresh}
        isRefreshing={isRefreshing}
        lastUpdated={lastUpdated}
      />

      {/* 2. Overview Metrics Grid: Total Volume + 8 Lifecycle Statuses */}
      <OverviewMetricsGrid
        totalEnquiries={metrics?.total_enquiries || 0}
        byStatus={metrics?.by_status || {}}
      />

      <PortalSummaryCards />

      {/* 3. Middle Section: Division Distribution (7 cols) & Recent Activity (5 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-stretch">
        <div className="lg:col-span-7">
          <DivisionDistributionCard
            divisions={metrics?.by_division || []}
            totalEnquiries={metrics?.total_enquiries || 0}
          />
        </div>
        <div className="lg:col-span-5">
          {activityError ? (
            <StatePartialData
              sectionName="Central Activity & Audit Feed"
              message={activityError}
              onRetry={handleRetryActivity}
              isRetrying={isRetryingActivity}
              className="h-full min-h-[300px]"
            />
          ) : (
            <RecentActivityFeed activities={activities} />
          )}
        </div>
      </div>

      {/* 4. Bottom Section: Strictly Read-Only Recent Commercial Enquiries (Max 5) */}
      {recentEnquiriesError ? (
        <StatePartialData
          sectionName="Recent Commercial Enquiries"
          message={recentEnquiriesError}
          onRetry={handleRetryRecent}
          isRetrying={isRetryingRecent}
        />
      ) : (
        <RecentEnquiriesCard enquiries={recentEnquiries} />
      )}
    </div>
  );
}
