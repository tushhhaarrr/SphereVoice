"use client";

/**
 * Node Palette — Drag-to-add panel of all 8 node types.
 *
 * Nodes are dragged from this panel onto the React Flow canvas.
 * Uses HTML5 drag and drop via onDragStart data transfer.
 */

import { type DragEvent, useCallback } from "react";
import {
  MessageSquare,
  Code,
  GitBranch,
  PhoneForwarded,
  Hash,
  Variable,
  MessageCircle,
  Square,
} from "lucide-react";
import type { FlowNodeType } from "../../types/flow";
import { NODE_TYPE_METADATA } from "../../types/flow";

const ICONS: Record<FlowNodeType, React.ElementType> = {
  conversation: MessageSquare,
  function: Code,
  logic_split: GitBranch,
  transfer: PhoneForwarded,
  press_digit: Hash,
  extract_variable: Variable,
  sms: MessageCircle,
  ending: Square,
};

interface NodePaletteProps {
  collapsed?: boolean;
}

export function NodePalette({ collapsed = false }: NodePaletteProps) {
  const onDragStart = useCallback(
    (event: DragEvent<HTMLDivElement>, nodeType: FlowNodeType) => {
      event.dataTransfer.setData("application/SphereVoice-flow-node", nodeType);
      event.dataTransfer.effectAllowed = "move";
    },
    []
  );

  if (collapsed) return null;

  return (
    <div className="flex h-full flex-col gap-2 bg-[#faf9f7] p-3">
      <div className="px-1 pb-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Nodes
        </p>
        <p className="mt-1 text-sm text-slate-500">
          Drag a node into the canvas.
        </p>
      </div>
      {Object.values(NODE_TYPE_METADATA).map((meta) => {
        const Icon = ICONS[meta.type];
        return (
          <div
            key={meta.type}
            draggable
            onDragStart={(e) => onDragStart(e, meta.type)}
            className={`
              group flex cursor-grab items-center gap-3 rounded-[18px] border border-slate-200 bg-white px-3 py-3 text-sm shadow-sm
              transition-colors hover:bg-slate-50 active:cursor-grabbing
            `}
          >
            <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 bg-slate-50`}>
              <Icon className={`h-4 w-4 ${meta.color}`} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="font-medium leading-none text-slate-900">{meta.label}</p>
              <p className="mt-1 text-[11px] leading-4 text-slate-500">
                {meta.description}
              </p>
            </div>
          </div>
        );
      })}
      <div className="mt-1 rounded-[18px] border border-dashed border-slate-200 bg-white px-3 py-3 text-[11px] leading-5 text-slate-500">
        Tip: start with a Conversation node, branch only when needed, and keep one clear ending path.
      </div>
    </div>
  );
}
