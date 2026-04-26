"use client";

import { Handle, type Position } from "@xyflow/react";
import type { CSSProperties, ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, GitBranch } from "lucide-react";
import { cn } from "@/lib/utils";

interface FlowNodeTone {
  iconBg: string;
  iconColor: string;
  selectedBorder: string;
  selectedRing: string;
  handle: string;
}

interface FlowNodeShellProps {
  icon: LucideIcon;
  typeLabel: string;
  title: string;
  selected?: boolean;
  tone: FlowNodeTone;
  badge?: ReactNode;
  summary?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  className?: string;
}

interface FlowNodeHandleProps {
  type: "source" | "target";
  position: Position;
  toneClass: string;
  id?: string;
  style?: CSSProperties;
}

export function FlowNodeShell({
  icon: Icon,
  typeLabel,
  title,
  selected = false,
  tone,
  badge,
  summary,
  footer,
  children,
  className,
}: FlowNodeShellProps) {
  return (
    <div
      className={cn(
        "relative min-w-[248px] max-w-[292px] overflow-hidden rounded-[20px] border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.05),0_10px_30px_rgba(15,23,42,0.06)] transition-all",
        selected && cn(tone.selectedBorder, tone.selectedRing, "ring-2"),
        className
      )}
    >
      <div className="px-3.5 pb-3.5 pt-3.5">
        <div className="flex items-start gap-3">
          <div className={cn("flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200", tone.iconBg)}>
            <Icon className={cn("h-4 w-4", tone.iconColor)} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <p className="truncate text-[15px] font-semibold leading-5 text-slate-900">
                  {title}
                </p>
                <span className="mt-0.5 block text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                  {typeLabel}
                </span>
              </div>
              {badge}
            </div>
          </div>
        </div>

        {summary ? (
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50/80 px-3 py-2.5 text-[11px] leading-5 text-slate-700">
            {summary}
          </div>
        ) : null}

        {children ? <div className="mt-3 space-y-2">{children}</div> : null}

        {footer ? (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function FlowNodeHandle({ type, position, toneClass, id, style }: FlowNodeHandleProps) {
  return (
    <Handle
      type={type}
      position={position}
      id={id}
      style={style}
      className={cn(
        "!h-2.5 !w-2.5 !border-2 !border-white !shadow-sm",
        toneClass
      )}
    />
  );
}

export function FlowNodePill({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] font-medium text-slate-600",
        className
      )}
    >
      {children}
    </span>
  );
}

export function FlowNodeSection({
  label,
  type = "transition",
  children,
}: {
  label: string;
  type?: "transition" | "branch";
  children: ReactNode;
}) {
  const Icon = type === "branch" ? GitBranch : ArrowRight;
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2.5">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
        <Icon className="h-3.5 w-3.5" />
        {label}
      </div>
      <div className="mt-2 space-y-1">{children}</div>
    </div>
  );
}

export function FlowNodeRouteRow({
  label,
  value,
  emphasized = false,
}: {
  label: string;
  value: ReactNode;
  emphasized?: boolean;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-2 rounded-xl px-2 py-1.5 text-[11px]",
        emphasized ? "bg-slate-50 text-slate-900" : "text-slate-600"
      )}
    >
      <span className="mt-1 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
      <span className="min-w-0 flex-1 leading-4">
        <span className="font-medium text-slate-900">{label}</span>
        <span className="text-slate-500"> {value}</span>
      </span>
    </div>
  );
}

export function FlowNodeBranchRow({
  index,
  label,
  value,
}: {
  index: number;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="flex items-start gap-2 rounded-xl px-2 py-1.5 text-[11px] text-slate-600">
      <span className="mt-1 inline-flex h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
      <div className="min-w-0 flex-1 leading-4">
        <div className="truncate font-medium text-slate-900">{label}</div>
        <div className="truncate text-slate-500">{value}</div>
      </div>
    </div>
  );
}

export const NODE_TONES = {
  conversation: {
    iconBg: "bg-blue-50",
    iconColor: "text-blue-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  function: {
    iconBg: "bg-violet-50",
    iconColor: "text-violet-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  logic: {
    iconBg: "bg-amber-50",
    iconColor: "text-amber-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  transfer: {
    iconBg: "bg-emerald-50",
    iconColor: "text-emerald-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  digit: {
    iconBg: "bg-cyan-50",
    iconColor: "text-cyan-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  extract: {
    iconBg: "bg-indigo-50",
    iconColor: "text-indigo-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  sms: {
    iconBg: "bg-pink-50",
    iconColor: "text-pink-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
  ending: {
    iconBg: "bg-rose-50",
    iconColor: "text-rose-700",
    selectedBorder: "border-slate-900",
    selectedRing: "ring-slate-200",
    handle: "!bg-slate-700",
  },
} as const;