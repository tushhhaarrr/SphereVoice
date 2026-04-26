/**
 * Call History Table — TanStack Table with server-side pagination,
 * sortable columns, and row-click to open call detail.
 *
 * Aligned with backend CallResponse schema (duration_seconds, total_cost).
 */

"use client";

import { useMemo } from "react";
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from "@tanstack/react-table";
import { useState } from "react";
import {
  ArrowUpDown,
  Loader2,
  Phone,
  PhoneIncoming,
  PhoneOff,
  PhoneOutgoing,
} from "lucide-react";
import { useEndCall, useExchangeRate } from "../hooks/use-calls";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { Call, CallStatus } from "../types";

// ── Constants ───────────────────────────────────────────────

const STATUS_STYLES: Record<CallStatus, string> = {
  queued: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  ringing:
    "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
  in_progress:
    "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
  completed:
    "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  failed: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
  no_answer: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const STATUS_LABELS: Record<CallStatus, string> = {
  queued: "Queued",
  ringing: "Ringing",
  in_progress: "In Progress",
  completed: "Completed",
  failed: "Failed",
  no_answer: "No Answer",
};

// ── Helpers ─────────────────────────────────────────────────

function formatDuration(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  const date = new Date(dateStr);
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  }).format(date);
}

function formatPhone(phone: string): string {
  if (phone.length === 12 && phone.startsWith("+1")) {
    return `+1 (${phone.slice(2, 5)}) ${phone.slice(5, 8)}-${phone.slice(8)}`;
  }
  return phone;
}

// ── Column Definition ───────────────────────────────────────

const columnHelper = createColumnHelper<Call>();

// ── Component ───────────────────────────────────────────────

interface CallHistoryTableProps {
  data: Call[];
  total: number;
  page: number;
  limit: number;
  isLoading: boolean;
  onPageChange: (page: number) => void;
  onRowClick?: (callId: string) => void;
}

export function CallHistoryTable({
  data,
  total,
  page,
  limit,
  isLoading,
  onPageChange,
  onRowClick,
}: CallHistoryTableProps) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: "created_at", desc: true },
  ]);
  const endCall = useEndCall();
  const { data: rateData } = useExchangeRate();
  const inrRate = rateData ? Number(rateData.rate) : null;

  const totalPages = Math.max(1, Math.ceil(total / limit));

  const columns = useMemo(
    () => [
      columnHelper.accessor("direction", {
        header: "",
        cell: (info) =>
          info.getValue() === "inbound" ? (
            <PhoneIncoming className="h-4 w-4 text-green-500" />
          ) : (
            <PhoneOutgoing className="h-4 w-4 text-blue-500" />
          ),
        size: 40,
        enableSorting: false,
      }),
      columnHelper.accessor("from_number", {
        header: ({ column }) => (
          <Button
            variant="ghost"
            size="sm"
            className="-ml-3 h-8"
            onClick={() =>
              column.toggleSorting(column.getIsSorted() === "asc")
            }
          >
            From
            <ArrowUpDown className="ml-1 h-3.5 w-3.5" />
          </Button>
        ),
        cell: (info) => (
          <span className="font-mono text-sm">
            {formatPhone(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor("to_number", {
        header: "To",
        cell: (info) => (
          <span className="font-mono text-sm">
            {formatPhone(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor("agent_id", {
        header: "Agent",
        cell: (info) => (
          <span className="text-sm font-medium truncate max-w-[120px] block">
            {info.getValue()?.slice(0, 8)}...
          </span>
        ),
      }),
      columnHelper.accessor("status", {
        header: "Status",
        cell: (info) => {
          const status = info.getValue() as CallStatus;
          return (
            <Badge className={STATUS_STYLES[status] ?? STATUS_STYLES.queued}>
              {STATUS_LABELS[status] ?? status}
            </Badge>
          );
        },
      }),
      columnHelper.accessor("duration_seconds", {
        header: ({ column }) => (
          <Button
            variant="ghost"
            size="sm"
            className="-ml-3 h-8"
            onClick={() =>
              column.toggleSorting(column.getIsSorted() === "asc")
            }
          >
            Duration
            <ArrowUpDown className="ml-1 h-3.5 w-3.5" />
          </Button>
        ),
        cell: (info) => (
          <span className="font-mono text-sm">
            {formatDuration(info.getValue())}
          </span>
        ),
      }),
      columnHelper.accessor("total_cost", {
        header: "Cost",
        cell: (info) => {
          const cost = info.getValue();
          if (cost === null || cost === undefined)
            return <span className="text-muted-foreground">—</span>;
          const usd = Number(cost);
          return (
            <span className="font-mono text-sm tabular-nums">
              {inrRate ? `₹${(usd * inrRate).toFixed(2)}` : `$${usd.toFixed(4)}`}
            </span>
          );
        },
      }),
      columnHelper.accessor("turn_count", {
        header: "Turns",
        cell: (info) => (
          <span className="text-sm">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor("created_at", {
        header: ({ column }) => (
          <Button
            variant="ghost"
            size="sm"
            className="-ml-3 h-8"
            onClick={() =>
              column.toggleSorting(column.getIsSorted() === "asc")
            }
          >
            Date
            <ArrowUpDown className="ml-1 h-3.5 w-3.5" />
          </Button>
        ),
        cell: (info) => (
          <span className="text-sm text-muted-foreground">
            {formatDate(info.getValue())}
          </span>
        ),
      }),
      columnHelper.display({
        id: "actions",
        header: "",
        size: 80,
        cell: (info) => {
          const call = info.row.original;
          const isLive = call.status === "in_progress" || call.status === "ringing" || call.status === "queued";
          if (!isLive) return null;
          return (
            <Button
              variant="destructive"
              size="sm"
              className="h-7 px-2 text-xs"
              disabled={endCall.isPending}
              onClick={(e) => {
                e.stopPropagation();
                endCall.mutate(call.id);
              }}
            >
              <PhoneOff className="mr-1 h-3 w-3" />
              End
            </Button>
          );
        },
      }),
    ],
    [endCall, inrRate],
  );

  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  // ── Render ──────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-lg border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    style={{
                      width:
                        header.column.getSize() !== 150
                          ? header.column.getSize()
                          : undefined,
                    }}
                  >
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                        header.column.columnDef.header,
                        header.getContext(),
                      )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center"
                >
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Phone className="h-8 w-8" />
                    <p>No calls found.</p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => onRowClick?.(row.original.id)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          Page {page} of {totalPages} ({total} total calls)
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => onPageChange(page + 1)}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
