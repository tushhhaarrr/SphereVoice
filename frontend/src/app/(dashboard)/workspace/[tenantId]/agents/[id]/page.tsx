"use client";

import { useParams } from "next/navigation";

import { AgentDetailPage } from "@/modules/agents";

export default function TenantWorkspaceAgentDetailPage() {
  const params = useParams<{ tenantId: string; id: string }>();

  return (
    <AgentDetailPage
      agentId={params.id}
      backHref={`/workspace/${params.tenantId}/agents`}
    />
  );
}