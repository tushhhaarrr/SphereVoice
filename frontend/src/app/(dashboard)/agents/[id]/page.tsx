"use client";

import { useParams } from "next/navigation";

import { AgentDetailPage } from "@/modules/agents";

export default function AgentDetailRoutePage() {
  const params = useParams<{ id: string }>();

  return <AgentDetailPage agentId={params.id} backHref="/agents" />;
}
