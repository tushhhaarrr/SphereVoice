"use client";

import { useParams } from "next/navigation";

import { CampaignDashboard } from "@/modules/campaigns";

export default function TenantWorkspaceCampaignDetailPage() {
    const params = useParams<{ tenantId: string; id: string }>();
    const tenantId = params.tenantId;
    const campaignId = params.id;

    return (
        <div className="space-y-6">
            <CampaignDashboard campaignId={campaignId} tenantId={tenantId} />
        </div>
    );
}
