"use client";

/**
 * Conversation Node — AI speaks and listens.
 *
 * Has one input handle (top) and one output handle (bottom).
 * Entry nodes get a special "START" badge.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { MessageSquare } from "lucide-react";
import type { ConversationNodeData } from "../../../types/flow";
import { FlowNodeHandle, FlowNodePill, FlowNodeRouteRow, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

function ConversationNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ConversationNodeData;

  return (
    <div className="relative">
      <FlowNodeHandle
        type="target"
        position={Position.Top}
        toneClass={NODE_TONES.conversation.handle}
      />
      <FlowNodeShell
        icon={MessageSquare}
        typeLabel="Conversation"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.conversation}
        badge={nodeData.isEntryNode ? <FlowNodePill className="border-sky-200 bg-sky-50 text-sky-700">Start</FlowNodePill> : undefined}
        summary={
          nodeData.instructions ||
          "Guide the caller, ask a focused question, and wait for the next response."
        }
        footer={nodeData.voiceOverride ? <FlowNodePill>Voice override</FlowNodePill> : <FlowNodePill>Conversation step</FlowNodePill>}
      >
        <FlowNodeSection label="Transition">
          <FlowNodeRouteRow label="On reply" value="Continue to next step" emphasized />
          <FlowNodeRouteRow label="Timeout" value={`${nodeData.timeoutSeconds}s silence window`} />
        </FlowNodeSection>
      </FlowNodeShell>
      <FlowNodeHandle
        type="source"
        position={Position.Bottom}
        toneClass={NODE_TONES.conversation.handle}
      />
    </div>
  );
}

export const ConversationNode = memo(ConversationNodeComponent);
