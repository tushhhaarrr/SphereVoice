"use client";

import { useEffect, useRef, useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { campaignKeys } from "./use-campaigns";
import type { CampaignStats } from "../types";

/**
 * useCampaignStream — polls the campaign stats endpoint every `intervalMs`
 * while the campaign is in an active state (running / paused / loading_contacts).
 *
 * Auto-invalidates TanStack Query caches so the UI updates in real time
 * without manual refresh.
 */
export function useCampaignStream(
    campaignId: string | null,
    status: string | null | undefined,
    intervalMs = 5000,
) {
    const queryClient = useQueryClient();
    const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const isActive = status === "running" || status === "paused" || status === "loading_contacts";

    const invalidate = useCallback(() => {
        if (!campaignId) return;
        queryClient.invalidateQueries({ queryKey: campaignKeys.stats(campaignId) });
        queryClient.invalidateQueries({ queryKey: campaignKeys.detail(campaignId) });
        queryClient.invalidateQueries({ queryKey: campaignKeys.contacts(campaignId) });
    }, [campaignId, queryClient]);

    useEffect(() => {
        if (!isActive || !campaignId) {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
            return;
        }

        // Start polling
        timerRef.current = setInterval(invalidate, intervalMs);

        return () => {
            if (timerRef.current) {
                clearInterval(timerRef.current);
                timerRef.current = null;
            }
        };
    }, [isActive, campaignId, intervalMs, invalidate]);
}
