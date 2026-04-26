"use client";

/**
 * SMS Node — Sends SMS during the call.
 *
 * Displays target number and message template.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { MessageCircle } from "lucide-react";
import type { SmsNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

function SmsNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as SmsNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.sms.handle} />
      <FlowNodeShell
        icon={MessageCircle}
        typeLabel="SMS"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.sms}
        badge={nodeData.useCallerNumber ? <FlowNodePill className="border-pink-200 bg-pink-50 text-pink-700">Caller</FlowNodePill> : undefined}
        summary={nodeData.messageTemplate || "Send a follow-up text during the call flow."}
        footer={
          nodeData.useCallerNumber ? (
            <FlowNodePill>Uses caller number</FlowNodePill>
          ) : nodeData.toNumber ? (
            <FlowNodePill>{nodeData.toNumber}</FlowNodePill>
          ) : (
            <FlowNodePill>No recipient set</FlowNodePill>
          )
        }
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="Recipient" value={nodeData.useCallerNumber ? "Caller number" : nodeData.toNumber || "No recipient"} emphasized />
          <FlowNodeRouteRow label="After SMS" value="Continue to next step" />
        </FlowNodeSection>
      </FlowNodeShell>
      <FlowNodeHandle type="source" position={Position.Bottom} toneClass={NODE_TONES.sms.handle} />
    </div>
  );
}

export const SmsNode = memo(SmsNodeComponent);
