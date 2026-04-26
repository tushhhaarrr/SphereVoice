"use client";

/**
 * Ending Node — Terminates the conversation.
 *
 * Terminal node — has input handle but no output.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { Square } from "lucide-react";
import type { EndingNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

const REASON_LABELS: Record<string, string> = {
  completed: "Completed",
  transferred: "Transferred",
  error: "Error",
  no_response: "No Response",
  custom: "Custom",
};

function EndingNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as EndingNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.ending.handle} />
      <FlowNodeShell
        icon={Square}
        typeLabel="Ending"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.ending}
        summary={nodeData.endingMessage || "Close the conversation and finish the call gracefully."}
        footer={<FlowNodePill className="border-rose-200 bg-rose-50 text-rose-700">{REASON_LABELS[nodeData.reason] || nodeData.reason}</FlowNodePill>}
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="End state" value={REASON_LABELS[nodeData.reason] || nodeData.reason} emphasized />
        </FlowNodeSection>
      </FlowNodeShell>
    </div>
  );
}

export const EndingNode = memo(EndingNodeComponent);
