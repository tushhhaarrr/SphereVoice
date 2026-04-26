"use client";

import { useParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useTenant } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";
import { KnowledgeBaseList } from "@/modules/knowledge-base";

export default function TenantWorkspaceKnowledgeBasePage() {
  const params = useParams<{ tenantId: string }>();
  const tenantId = params.tenantId;
  const { isAdmin, isLoading } = useAuth();
  const tenant = useTenant(tenantId, isAdmin && !isLoading);

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Knowledge Base Scope</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            This workspace only surfaces knowledge bases owned by {tenant.data?.name ?? "this tenant"}
            {" "}plus Gorillaa-wide global collections.
          </p>
          <p>
            New knowledge bases created here default to tenant scope so retrieval content stays attached to the
            correct client boundary.
          </p>
        </CardContent>
      </Card>

      <KnowledgeBaseList tenantId={tenantId} tenantName={tenant.data?.name} />
    </div>
  );
}