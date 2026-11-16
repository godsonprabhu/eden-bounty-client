"use client";

import { useGlobalUIState } from "@/context/GlobalUIStateContext";

export function useNetworkStatus() {
  const { isOnline, wasOffline, reconnectedAt, dismissReconnectedBanner } = useGlobalUIState();
  return {
    isOnline,
    wasOffline,
    isReconnected: !!reconnectedAt,
    reconnectedAt,
    dismissReconnectedBanner,
  };
}
