"use client";

/**
 * Logic Split Node — Branches based on conditions.
 *
 * Has one input (top) and multiple output handles (bottom),
 * one per condition plus a default.
 */

import { memo } from "react";
import { Position, type NodeProps } from "@xyflow/react";
import { GitBranch } from "lucide-react";
import type { LogicSplitNodeData } from "../../../types/flow";
import { FlowNodeBranchRow, FlowNodeHandle, FlowNodePill, FlowNodeSection, FlowNodeShell, NODE_TONES } from "./shared";

function LogicSplitNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as LogicSplitNodeData;
  const conditionCount = nodeData.conditions.length;
  const totalOutputs = conditionCount + 1; // +1 for default

  return (
    <div className="relative">
      <FlowNodeHandle type="target" position={Position.Top} toneClass={NODE_TONES.logic.handle} />
      <FlowNodeShell
        icon={GitBranch}
        typeLabel="Logic Split"
        title={nodeData.label}
        selected={selected}
        tone={NODE_TONES.logic}
        summary={conditionCount > 0 ? `Route the caller based on ${conditionCount} condition${conditionCount !== 1 ? "s" : ""}.` : "Branch the flow based on caller answers or extracted variables."}
        footer={
          <>
            <FlowNodePill>{totalOutputs} path{totalOutputs !== 1 ? "s" : ""}</FlowNodePill>
            <FlowNodePill>Default fallback</FlowNodePill>
          </>
        }
      >
        <FlowNodeSection label="Transition" type="branch">
          {conditionCount > 0 ? (
            nodeData.conditions.slice(0, 3).map((cond, i) => (
              <FlowNodeBranchRow
                key={cond.id}
                index={i + 1}
                label={cond.variableName || `Condition ${i + 1}`}
                value={`${cond.operator.replace(/_/g, " ")} ${cond.value || "value"}`}
              />
            ))
          ) : (
            <div className="rounded-xl px-2 py-1.5 text-[11px] text-slate-500">
              Add conditions to send callers down different paths.
            </div>
          )}
          <FlowNodeBranchRow index={conditionCount + 1} label="Default" value={nodeData.defaultPath || "Fallback path"} />
        </FlowNodeSection>
      </FlowNodeShell>

      {Array.from({ length: totalOutputs }, (_, i) => (
        <FlowNodeHandle
          key={`output-${i}`}
          type="source"
          position={Position.Bottom}
          id={`output-${i}`}
          toneClass={NODE_TONES.logic.handle}
          style={{ left: `${((i + 1) / (totalOutputs + 1)) * 100}%` }}
        />
      ))}
    </div>
  );
}

export const LogicSplitNode = memo(LogicSplitNodeComponent);
