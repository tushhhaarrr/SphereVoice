"use client";

import { useParams } from "next/navigation";

import { CampaignWizard } from "@/modules/campaigns";

export default function TenantWorkspaceNewCampaignPage() {
    const params = useParams<{ tenantId: string }>();
    const tenantId = params.tenantId;

    return (
        <div className="space-y-6">
            <CampaignWizard tenantId={tenantId} />
        </div>
    );
}
