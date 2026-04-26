"use client";

import { useParams } from "next/navigation";

import { useAuth } from "@/modules/auth";
import { CampaignDashboard } from "@/modules/campaigns";

export default function CampaignDetailPage() {
    const params = useParams<{ id: string }>();
    const { user } = useAuth();
    const tenantId = user?.tenantId;
    const campaignId = params.id;

    if (!tenantId) {
        return (
            <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
                Select a tenant workspace to view this campaign.
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <CampaignDashboard campaignId={campaignId} tenantId={tenantId} />
        </div>
    );
}
