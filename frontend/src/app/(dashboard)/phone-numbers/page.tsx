/**
 * Phone Numbers page — search, purchase, manage, assign agents.
 */

"use client";

import { useState } from "react";
import {
  PhoneNumbersTable,
  SearchNumbersDialog,
  AssignAgentDialog,
  usePhoneNumbers,
  useReleaseNumber,
  useSyncPlivoNumbers,
  useSetDefaultOutbound,
  useClearDefaultOutbound,
} from "@/modules/phone-numbers";
import type { PhoneNumberListParams, PhoneNumber } from "@/modules/phone-numbers";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Phone, RefreshCw } from "lucide-react";

export default function PhoneNumbersPage() {
  const [params, setParams] = useState<PhoneNumberListParams>({
    page: 1,
    limit: 20,
  });
  const [statusFilter, setStatusFilter] = useState<string>("all");

  // Assign dialog state
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedNumberId, setSelectedNumberId] = useState("");
  const [selectedPhoneNumber, setSelectedPhoneNumber] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const effectiveParams: PhoneNumberListParams = {
    ...params,
    status: statusFilter !== "all" ? (statusFilter as "active" | "inactive") : undefined,
  };

  const { data, isLoading } = usePhoneNumbers(effectiveParams);
  const releaseMutation = useReleaseNumber();
  const syncMutation = useSyncPlivoNumbers();
  const setDefaultMutation = useSetDefaultOutbound();
  const clearDefaultMutation = useClearDefaultOutbound();

  function handlePageChange(page: number) {
    setParams((prev) => ({ ...prev, page }));
  }

  function handleAssign(number: PhoneNumber) {
    setSelectedNumberId(number.id);
    setSelectedPhoneNumber(number.phone_number);
    setSelectedAgentId(number.agent_id);
    setAssignDialogOpen(true);
  }

  function handleRelease(number: PhoneNumber) {
    if (window.confirm("Are you sure you want to release this phone number?")) {
      releaseMutation.mutate(number.id);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Phone className="h-6 w-6" />
            Phone Numbers
          </h1>
          <p className="text-muted-foreground mt-1">
            Purchase and manage phone numbers for your voice agents.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium hover:bg-accent disabled:opacity-50"
            disabled={syncMutation.isPending}
            onClick={() => syncMutation.mutate()}
            title="Import numbers rented on Plivo that aren't in SphereVoice yet"
          >
            <RefreshCw className={`h-4 w-4 ${syncMutation.isPending ? "animate-spin" : ""}`} />
            Sync Plivo
          </button>
          <SearchNumbersDialog tenantId="" />
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Numbers</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{data?.total ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {data?.numbers?.filter((n) => n.status === "active").length ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Assigned to Agents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {data?.numbers?.filter((n) => n.agent_id !== null).length ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="inactive">Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <PhoneNumbersTable
        data={data?.numbers ?? []}
        total={data?.total ?? 0}
        page={params.page ?? 1}
        limit={params.limit ?? 20}
        isLoading={isLoading}
        showTenant
        onPageChange={handlePageChange}
        onAssign={handleAssign}
        onRelease={handleRelease}
        onSetDefault={(n) => setDefaultMutation.mutate(n.id)}
        onClearDefault={(n) => clearDefaultMutation.mutate(n.id)}
      />

      {/* Assign Dialog */}
      <AssignAgentDialog
        open={assignDialogOpen}
        onOpenChange={setAssignDialogOpen}
        numberId={selectedNumberId}
        phoneNumber={selectedPhoneNumber}
        currentAgentId={selectedAgentId}
      />
    </div>
  );
}
