"use client";

/**
 * Extract Variable Node — Pulls structured data from conversation.
 *
 * Displays the variable name, type, and extraction prompt.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { Variable } from "lucide-react";
import type { ExtractVariableNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

const TYPE_BADGES: Record<string, string> = {
  text: "border-indigo-200 bg-indigo-50 text-indigo-700",
  number: "border-cyan-200 bg-cyan-50 text-cyan-700",
  boolean: "border-amber-200 bg-amber-50 text-amber-700",
  date: "border-pink-200 bg-pink-50 text-pink-700",
  email: "border-emerald-200 bg-emerald-50 text-emerald-700",
  phone: "border-violet-200 bg-violet-50 text-violet-700",
};

function ExtractVariableNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ExtractVariableNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.extract.handle} />
      <FlowNodeShell
        icon={Variable}
        typeLabel="Extract Variable"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.extract}
        badge={nodeData.required ? <FlowNodePill className="border-rose-200 bg-rose-50 text-rose-700">Required</FlowNodePill> : undefined}
        summary={nodeData.extractionPrompt || "Capture a structured field from the conversation and save it for later steps."}
        footer={
          <>
            {nodeData.variableName ? <FlowNodePill>{`{{${nodeData.variableName}}}`}</FlowNodePill> : null}
            <FlowNodePill className={TYPE_BADGES[nodeData.variableType] || ""}>{nodeData.variableType}</FlowNodePill>
          </>
        }
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="Save to" value={nodeData.variableName ? `{{${nodeData.variableName}}}` : "Unset variable"} emphasized />
          <FlowNodeRouteRow label="Retries" value={`${nodeData.maxRetries} attempt${nodeData.maxRetries !== 1 ? "s" : ""}`} />
        </FlowNodeSection>
      </FlowNodeShell>
      <FlowNodeHandle type="source" position={Position.Bottom} toneClass={NODE_TONES.extract.handle} />
    </div>
  );
}

export const ExtractVariableNode = memo(ExtractVariableNodeComponent);
