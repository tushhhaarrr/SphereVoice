"use client";

/**
 * Press Digit Node — Sends DTMF tones.
 *
 * Allows configuring digit sequence and delay.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { Hash } from "lucide-react";
import type { PressDigitNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

function PressDigitNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as PressDigitNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.digit.handle} />
      <FlowNodeShell
        icon={Hash}
        typeLabel="Press Digit"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.digit}
        summary={
          nodeData.digits ? (
            <span className="font-mono text-sm font-semibold text-cyan-700 dark:text-cyan-300">{nodeData.digits}</span>
          ) : (
            "Send DTMF tones to navigate an IVR menu or keypad prompt."
          )
        }
        footer={<FlowNodePill>{nodeData.delayMs}ms delay</FlowNodePill>}
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="Digits" value={nodeData.digits || "Not set"} emphasized />
          <FlowNodeRouteRow label="After send" value="Continue to next step" />
        </FlowNodeSection>
      </FlowNodeShell>
      <FlowNodeHandle type="source" position={Position.Bottom} toneClass={NODE_TONES.digit.handle} />
    </div>
  );
}

export const PressDigitNode = memo(PressDigitNodeComponent);
