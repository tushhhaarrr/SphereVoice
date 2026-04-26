/**
 * Phone Numbers Table — TanStack Table with status badges + agent assignment.
 */

"use client";

import { useState } from "react";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowUpDown, Phone, PhoneOff, Star, Trash2, UserPlus } from "lucide-react";

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

import { getProviderLabel } from "@/modules/providers/lib/catalog";

import type { PhoneNumber, PhoneNumberCapabilities } from "../types";

interface PhoneNumbersTableProps {
  data: PhoneNumber[];
  total: number;
  page: number;
  limit: number;
  isLoading?: boolean;
  /** Show Tenant column (admin global view) */
  showTenant?: boolean;
  onPageChange: (page: number) => void;
  onAssign: (number: PhoneNumber) => void;
  onRelease: (number: PhoneNumber) => void;
  onSetDefault?: (number: PhoneNumber) => void;
  onClearDefault?: (number: PhoneNumber) => void;
}

function StatusBadge({ status }: { status: string }) {
  const variant = status === "active" ? "default" : "secondary";
  return <Badge variant={variant}>{status}</Badge>;
}

function CapabilitiesBadges({
  capabilities,
}: {
  capabilities: PhoneNumberCapabilities;
}) {
  return (
    <div className="flex gap-1">
      {capabilities.voice && (
        <Badge variant="outline" className="text-xs">
          Voice
        </Badge>
      )}
      {capabilities.sms && (
        <Badge variant="outline" className="text-xs">
          SMS
        </Badge>
      )}
      {capabilities.mms && (
        <Badge variant="outline" className="text-xs">
          MMS
        </Badge>
      )}
    </div>
  );
}

export function PhoneNumbersTable({
  data,
  total,
  page,
  limit,
  isLoading,
  showTenant,
  onPageChange,
  onAssign,
  onRelease,
  onSetDefault,
  onClearDefault,
}: PhoneNumbersTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  const columns: ColumnDef<PhoneNumber>[] = [
    {
      accessorKey: "phone_number",
      header: ({ column }) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => column.toggleSorting(column.getIsSorted() === "asc")}
        >
          <Phone className="mr-1 h-4 w-4" />
          Number
          <ArrowUpDown className="ml-1 h-3 w-3" />
        </Button>
      ),
      cell: ({ row }) => (
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm">{row.original.phone_number}</span>
          {row.original.is_default_outbound && (
            <Badge variant="default" className="gap-1 text-[10px] px-1.5 py-0 h-5 bg-amber-500 hover:bg-amber-500">
              <Star className="h-2.5 w-2.5 fill-current" />
              Default
            </Badge>
          )}
        </div>
      ),
    },
    {
      accessorKey: "country_code",
      header: "Country",
      cell: ({ row }) => row.original.country_code ?? "—",
    },
    ...(showTenant
      ? [
        {
          accessorKey: "tenant_name",
          header: "Tenant",
          cell: ({ row }: { row: { original: PhoneNumber } }) =>
            row.original.tenant_name ? (
              <span className="text-sm font-medium">{row.original.tenant_name}</span>
            ) : (
              <span className="text-muted-foreground text-xs">—</span>
            ),
        } satisfies ColumnDef<PhoneNumber>,
      ]
      : []),
    {
      accessorKey: "provider_name",
      header: "Provider",
      cell: ({ row }) => (
        <Badge variant="outline" className="capitalize">
          {getProviderLabel(row.original.provider_name)}
        </Badge>
      ),
    },
    {
      accessorKey: "capabilities",
      header: "Capabilities",
      cell: ({ row }) => (
        <CapabilitiesBadges capabilities={row.original.capabilities} />
      ),
      enableSorting: false,
    },
    {
      accessorKey: "agent_id",
      header: "Assigned Agent",
      cell: ({ row }) =>
        row.original.agent_name ? (
          <Badge variant="default" className="text-xs">
            {row.original.agent_name}
          </Badge>
        ) : row.original.agent_id ? (
          <Badge variant="default" className="text-xs">
            {row.original.agent_id.slice(0, 8)}…
          </Badge>
        ) : (
          <span className="text-muted-foreground text-xs">Unassigned</span>
        ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => <StatusBadge status={row.original.status} />,
    },
    {
      accessorKey: "monthly_cost",
      header: "Monthly Cost",
      cell: ({ row }) =>
        row.original.monthly_cost != null
          ? `$${Number(row.original.monthly_cost).toFixed(2)}`
          : "—",
    },
    {
      accessorKey: "purchased_at",
      header: "Purchased",
      cell: ({ row }) =>
        new Date(row.original.purchased_at).toLocaleDateString(),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex gap-1">
          {(onSetDefault || onClearDefault) && (
            <Button
              variant="ghost"
              size="icon"
              className={`h-8 w-8 ${row.original.is_default_outbound ? "text-amber-500" : ""}`}
              title={row.original.is_default_outbound ? "Remove as default outbound" : "Set as default outbound"}
              onClick={() =>
                row.original.is_default_outbound
                  ? onClearDefault?.(row.original)
                  : onSetDefault?.(row.original)
              }
            >
              <Star className={`h-4 w-4 ${row.original.is_default_outbound ? "fill-current" : ""}`} />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            title={row.original.agent_id ? "Reassign agent" : "Assign agent"}
            onClick={() => onAssign(row.original)}
          >
            <UserPlus className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive"
            title="Release number"
            onClick={() => onRelease(row.original)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
      enableSorting: false,
    },
  ];

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    onSortingChange: setSorting,
    state: { sorting },
  });

  const totalPages = Math.ceil(total / limit);

  return (
    <div className="space-y-4">
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
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
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  Loading phone numbers…
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  <div className="flex flex-col items-center gap-2">
                    <PhoneOff className="h-8 w-8 text-muted-foreground" />
                    <p className="text-muted-foreground">No phone numbers yet</p>
                    <p className="text-xs text-muted-foreground">
                      Purchase a number to get started
                    </p>
                  </div>
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow key={row.id}>
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
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            Showing {(page - 1) * limit + 1}–
            {Math.min(page * limit, total)} of {total}
          </p>
          <div className="flex gap-2">
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
      )}
    </div>
  );
}
