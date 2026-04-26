"use client";

import { RetellTemplateImportDialog, TemplateGallery } from "@/modules/analytics";
import { useTemplates } from "@/modules/analytics/hooks/use-templates";
import { useAuth } from "@/modules/auth/hooks/use-auth";

export default function TemplatesPage() {
    const { user } = useAuth();
    const templates = useTemplates();

    return (
        <div className="space-y-6 p-8">
            <div className="flex items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold">Agent Templates</h1>
                    <p className="text-muted-foreground mt-1">
                        Pre-built and custom templates to quickly create voice agents
                    </p>
                </div>
                <RetellTemplateImportDialog />
            </div>

            <TemplateGallery
                data={templates.data}
                isLoading={templates.isLoading}
                tenantId={user?.tenantId || undefined}
            />
        </div>
    );
}
