"use client";

/**
 * Call Transfer Node — Transfers to human or phone number.
 *
 * Terminal node — has input handle but no output.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { PhoneForwarded } from "lucide-react";
import type { TransferNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

function TransferNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as TransferNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.transfer.handle} />
      <FlowNodeShell
        icon={PhoneForwarded}
        typeLabel="Call Transfer"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.transfer}
        badge={nodeData.warmTransfer ? <FlowNodePill className="border-emerald-200 bg-emerald-50 text-emerald-700">Warm</FlowNodePill> : undefined}
        summary={nodeData.transferMessage || "Transfer the caller to a live person or external number."}
        footer={nodeData.transferTo ? <FlowNodePill>{nodeData.transferTo}</FlowNodePill> : <FlowNodePill>No destination set</FlowNodePill>}
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="Destination" value={nodeData.transferTo || "Choose a number"} emphasized />
          <FlowNodeRouteRow label="Mode" value={nodeData.warmTransfer ? "Warm transfer" : "Cold transfer"} />
        </FlowNodeSection>
      </FlowNodeShell>
    </div>
  );
}

export const TransferNode = memo(TransferNodeComponent);
