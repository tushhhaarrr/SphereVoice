"use client";

import { useState } from "react";
import { Phone } from "lucide-react";
import { RefreshCw } from "lucide-react";
import { useParams } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTenant } from "@/modules/analytics";
import { useAuth } from "@/modules/auth";
import {
  AssignAgentDialog,
  PhoneNumbersTable,
  SearchNumbersDialog,
  usePhoneNumbers,
  useReleaseNumber,
  useSyncPlivoNumbers,
} from "@/modules/phone-numbers";
import type { PhoneNumber, PhoneNumberListParams } from "@/modules/phone-numbers";

export default function TenantWorkspacePhoneNumbersPage() {
  const params = useParams<{ tenantId: string }>();
  const tenantId = params.tenantId;
  const { isAdmin, isLoading: authLoading } = useAuth();
  const tenant = useTenant(tenantId, isAdmin && !authLoading);

  const [paramsState, setParamsState] = useState<PhoneNumberListParams>({
    page: 1,
    limit: 20,
    tenant_id: tenantId,
  });
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [assignDialogOpen, setAssignDialogOpen] = useState(false);
  const [selectedNumberId, setSelectedNumberId] = useState("");
  const [selectedPhoneNumber, setSelectedPhoneNumber] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);

  const effectiveParams: PhoneNumberListParams = {
    ...paramsState,
    tenant_id: tenantId,
    status: statusFilter !== "all" ? (statusFilter as "active" | "inactive") : undefined,
  };

  const { data, isLoading } = usePhoneNumbers(effectiveParams);
  const releaseMutation = useReleaseNumber();
  const syncMutation = useSyncPlivoNumbers();

  function handlePageChange(page: number) {
    setParamsState((prev) => ({ ...prev, page }));
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
      <Card>
        <CardHeader>
          <CardTitle>Phone Number Scope</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          <p>
            This workspace only shows numbers owned by {tenant.data?.name ?? "this tenant"}.
          </p>
          <p>
            New purchases made here are attached directly to the tenant so number assignment and routing stay inside the correct client boundary.
          </p>
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-bold">
            <Phone className="h-6 w-6" />
            Phone Numbers
          </h1>
          <p className="mt-1 text-muted-foreground">
            Purchase and manage numbers for {tenant.data?.name ?? "this workspace"}.
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
          <SearchNumbersDialog tenantId={tenantId} tenantName={tenant.data?.name} />
        </div>
      </div>

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

      <PhoneNumbersTable
        data={data?.numbers ?? []}
        total={data?.total ?? 0}
        page={paramsState.page ?? 1}
        limit={paramsState.limit ?? 20}
        isLoading={isLoading}
        onPageChange={handlePageChange}
        onAssign={handleAssign}
        onRelease={handleRelease}
      />

      <AssignAgentDialog
        open={assignDialogOpen}
        onOpenChange={setAssignDialogOpen}
        numberId={selectedNumberId}
        phoneNumber={selectedPhoneNumber}
        currentAgentId={selectedAgentId}
        tenantId={tenantId}
        tenantName={tenant.data?.name}
      />
    </div>
  );
}