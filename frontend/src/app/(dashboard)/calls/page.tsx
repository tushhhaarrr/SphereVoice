/**
 * Call History page — list calls with filters, search, export, and detail modal.
 */

"use client";

import { useState } from "react";
import {
  Download,
  Phone,
  Search,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import {
  CallHistoryTable,
  CallDetailModal,
  useCalls,
  type CallListParams,
} from "@/modules/calls";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:2998";

export default function CallsPage() {
  const [params, setParams] = useState<CallListParams>({
    page: 1,
    limit: 20,
  });
  const [statusFilter, setStatusFilter] = useState("all");
  const [directionFilter, setDirectionFilter] = useState("all");
  const [searchText, setSearchText] = useState("");

  // Detail modal
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const effectiveParams: CallListParams = {
    ...params,
    status: statusFilter !== "all" ? (statusFilter as CallListParams["status"]) : undefined,
    direction: directionFilter !== "all" ? (directionFilter as CallListParams["direction"]) : undefined,
    search: searchText || undefined,
  };

  const { data, isLoading } = useCalls(effectiveParams);

  function handlePageChange(page: number) {
    setParams((prev) => ({ ...prev, page }));
  }

  function handleRowClick(callId: string) {
    setSelectedCallId(callId);
    setDetailOpen(true);
  }

  function handleExport(format: "csv" | "json") {
    const sp = new URLSearchParams();
    sp.set("format", format);
    if (effectiveParams.status) sp.set("status", effectiveParams.status);
    if (effectiveParams.direction) sp.set("direction", effectiveParams.direction);
    if (effectiveParams.search) sp.set("search", effectiveParams.search);
    window.open(`${API_BASE}/api/v1/calls/export?${sp.toString()}`, "_blank");
  }

  function handleSearch() {
    setParams((prev) => ({ ...prev, page: 1 }));
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Phone className="h-6 w-6" />
            Call History
          </h1>
          <p className="text-muted-foreground mt-1">
            View and analyze all voice agent calls.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => handleExport("csv")}>
            <Download className="mr-2 h-4 w-4" />
            CSV
          </Button>
          <Button variant="outline" size="sm" onClick={() => handleExport("json")}>
            <Download className="mr-2 h-4 w-4" />
            JSON
          </Button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by phone number..."
            className="pl-9 w-[250px]"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleSearch();
            }}
          />
        </div>

        <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setParams((p) => ({ ...p, page: 1 })); }}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="queued">Queued</SelectItem>
            <SelectItem value="ringing">Ringing</SelectItem>
            <SelectItem value="in_progress">In Progress</SelectItem>
            <SelectItem value="completed">Completed</SelectItem>
            <SelectItem value="failed">Failed</SelectItem>
            <SelectItem value="no_answer">No Answer</SelectItem>
          </SelectContent>
        </Select>

        <Select value={directionFilter} onValueChange={(v) => { setDirectionFilter(v); setParams((p) => ({ ...p, page: 1 })); }}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Direction" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Directions</SelectItem>
            <SelectItem value="inbound">Inbound</SelectItem>
            <SelectItem value="outbound">Outbound</SelectItem>
          </SelectContent>
        </Select>

        <Badge variant="secondary">
          {data?.total ?? 0} total
        </Badge>
      </div>

      {/* Table */}
      <CallHistoryTable
        data={data?.calls ?? []}
        total={data?.total ?? 0}
        page={params.page ?? 1}
        limit={params.limit ?? 20}
        isLoading={isLoading}
        onPageChange={handlePageChange}
        onRowClick={handleRowClick}
      />

      {/* Detail Modal */}
      <CallDetailModal
        callId={selectedCallId}
        open={detailOpen}
        onOpenChange={setDetailOpen}
      />
    </div>
  );
}
