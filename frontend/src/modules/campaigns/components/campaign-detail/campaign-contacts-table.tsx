"use client";

import { useState } from "react";
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  createColumnHelper,
} from "@tanstack/react-table";
import { Headset, RotateCw, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useCampaignContacts, useRetryContact } from "../../hooks/use-campaigns";
import {
  getContactStatusColor,
  formatPhoneNumber,
  formatDateTime,
} from "../../lib/campaign-utils";
import type { CampaignContactListItem, CampaignContactStatus } from "../../types";
import { ContactDetailDialog } from "./contact-detail-dialog";
import { ContactTestCallDialog } from "./contact-test-call-dialog";

interface CampaignContactsTableProps {
  campaignId: string;
  tenantId?: string;
}

/** Extract a display-friendly value from contact_data by checking common CRM field names. */
function getContactField(
  data: Record<string, unknown> | undefined,
  ...keys: string[]
): string | null {
  if (!data) return null;
  for (const key of keys) {
    const val = data[key];
    if (val !== undefined && val !== null && String(val).trim() !== "") {
      return String(val);
    }
  }
  return null;
}

const columnHelper = createColumnHelper<CampaignContactListItem>();

export function CampaignContactsTable({ campaignId, tenantId }: CampaignContactsTableProps) {
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<CampaignContactStatus | "all">("all");
  const [selectedContactId, setSelectedContactId] = useState<string | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [testCallContactId, setTestCallContactId] = useState<string | null>(null);
  const [testCallOpen, setTestCallOpen] = useState(false);

  const contacts = useCampaignContacts(campaignId, {
    page,
    limit: 20,
    status: statusFilter === "all" ? undefined : statusFilter,
  }, tenantId);

  const retryContact = useRetryContact(campaignId, tenantId);

  const columns = [
    columnHelper.display({
      id: "contact_name",
      header: "Contact",
      cell: (info) => {
        const row = info.row.original;
        const cd = row.contact_data;
        const name = getContactField(cd, "Full_Name", "full_name", "name", "Name", "First_Name", "first_name", "Last_Name", "last_name");
        const company = getContactField(cd, "Company", "company", "Account_Name", "account_name", "Organization", "organization");
        return (
          <div className="flex items-center gap-3 min-w-[180px]">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-muted-foreground shrink-0">
              <User className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">
                {name ?? "Unknown Contact"}
              </p>
              {company && (
                <p className="text-xs text-muted-foreground truncate">{company}</p>
              )}
            </div>
          </div>
        );
      },
    }),
    columnHelper.accessor("phone_number", {
      header: "Phone",
      cell: (info) => (
        <span className="font-mono text-sm">{formatPhoneNumber(info.getValue())}</span>
      ),
    }),
    columnHelper.display({
      id: "email",
      header: "Email",
      cell: (info) => {
        const cd = info.row.original.contact_data;
        const email = getContactField(cd, "Email", "email", "Email_Address", "email_address");
        return (
          <span className="text-sm text-muted-foreground truncate max-w-[200px] block">
            {email ?? "—"}
          </span>
        );
      },
    }),
    columnHelper.accessor("status", {
      header: "Status",
      cell: (info) => {
        const status = info.getValue();
        const colors = getContactStatusColor(status);
        return (
          <Badge variant="outline" className={`${colors.bg} ${colors.text} border-0`}>
            <span className={`mr-1.5 h-1.5 w-1.5 rounded-full ${colors.dot}`} />
            {status.replace("_", " ")}
          </Badge>
        );
      },
    }),
    columnHelper.accessor("attempt_count", {
      header: "Attempts",
      cell: (info) => <span className="tabular-nums">{info.getValue()}</span>,
    }),
    columnHelper.accessor("call_id", {
      header: "Call ID",
      cell: (info) => {
        const v = info.getValue();
        return (
          <span className="font-mono text-xs text-muted-foreground">
            {v ? v.slice(0, 8) : "—"}
          </span>
        );
      },
    }),
    columnHelper.display({
      id: "actions",
      header: "",
      cell: (info) => {
        const row = info.row.original;
        const canRetry = row.status === "failed" || row.status === "retry_scheduled";
        return (
          <div className="flex items-center gap-1">
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 gap-1.5 text-xs"
                    onClick={(e) => {
                      e.stopPropagation();
                      setTestCallContactId(row.id);
                      setTestCallOpen(true);
                    }}
                  >
                    <Headset className="h-3.5 w-3.5" />
                    Test
                  </Button>
                </TooltipTrigger>
                <TooltipContent>
                  <p>Browser test call — speak to the AI agent using this contact&apos;s data</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
            {canRetry && (
              <Button
                variant="ghost"
                size="sm"
                disabled={retryContact.isPending}
                onClick={(e) => {
                  e.stopPropagation();
                  retryContact.mutate(row.id);
                }}
              >
                <RotateCw className="mr-1 h-3 w-3" />
                Retry
              </Button>
            )}
          </div>
        );
      },
    }),
  ];

  const table = useReactTable({
    data: contacts.data?.contacts ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const totalPages = Math.ceil((contacts.data?.total ?? 0) / 20);

  return (
    <div className="space-y-4">
      {/* Filter bar */}
      <div className="flex items-center gap-3">
        <Select
          value={statusFilter}
          onValueChange={(v) => {
            setStatusFilter(v as CampaignContactStatus | "all");
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="calling">Calling</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="retry_scheduled">Retry Scheduled</SelectItem>
            <SelectItem value="skipped">Skipped</SelectItem>
            <SelectItem value="cancelled">Cancelled</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">
          {contacts.data?.total ?? 0} contact{(contacts.data?.total ?? 0) !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  {contacts.isLoading ? "Loading contacts…" : "No contacts found."}
                </TableCell>
              </TableRow>
            ) : (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer hover:bg-muted/50"
                  onClick={() => {
                    setSelectedContactId(row.original.id);
                    setDialogOpen(true);
                  }}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
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
        <div className="flex items-center justify-end gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">
            Page {page} of {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      )}

      {/* Contact detail dialog */}
      <ContactDetailDialog
        campaignId={campaignId}
        tenantId={tenantId}
        contactId={selectedContactId}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
      />

      {/* Test call dialog */}
      {testCallContactId && (
        <ContactTestCallDialog
          campaignId={campaignId}
          tenantId={tenantId}
          contactId={testCallContactId}
          open={testCallOpen}
          onOpenChange={setTestCallOpen}
        />
      )}
    </div>
  );
}
