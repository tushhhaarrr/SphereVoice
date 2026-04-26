"use client";

import { useAuth } from "@/modules/auth";
import { CampaignWizard } from "@/modules/campaigns";

export default function NewCampaignPage() {
    const { user } = useAuth();
    const tenantId = user?.tenantId;

    if (!tenantId) {
        return (
            <div className="flex items-center justify-center py-20 text-sm text-muted-foreground">
                Select a tenant workspace to create a campaign.
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <CampaignWizard tenantId={tenantId} />
        </div>
    );
}
