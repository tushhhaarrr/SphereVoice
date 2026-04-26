"use client";

/**
 * Function Node — Calls an external API or webhook.
 *
 * Displays HTTP method badge and endpoint URL.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { Code } from "lucide-react";
import type { FunctionNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

const METHOD_COLORS: Record<string, string> = {
  GET: "border-emerald-200 bg-emerald-50 text-emerald-700",
  POST: "border-sky-200 bg-sky-50 text-sky-700",
  PUT: "border-amber-200 bg-amber-50 text-amber-700",
  DELETE: "border-rose-200 bg-rose-50 text-rose-700",
};

function FunctionNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as FunctionNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.function.handle} />
      <FlowNodeShell
        icon={Code}
        typeLabel="Function"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.function}
        summary={nodeData.endpointUrl || "Connect this step to a webhook or external API."}
        footer={
          <>
            <FlowNodePill className={METHOD_COLORS[nodeData.method] || ""}>{nodeData.method}</FlowNodePill>
            {nodeData.responseMapping.length > 0 ? (
              <FlowNodePill>{nodeData.responseMapping.length} mapping{nodeData.responseMapping.length !== 1 ? "s" : ""}</FlowNodePill>
            ) : null}
          </>
        }
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="Success" value="Continue after response" emphasized />
          <FlowNodeRouteRow label="Failure" value={nodeData.errorHandling.replace(/_/g, " ")} />
        </FlowNodeSection>
      </FlowNodeShell>
      <FlowNodeHandle type="source" position={Position.Bottom} toneClass={NODE_TONES.function.handle} />
    </div>
  );
}

export const FunctionNode = memo(FunctionNodeComponent);
