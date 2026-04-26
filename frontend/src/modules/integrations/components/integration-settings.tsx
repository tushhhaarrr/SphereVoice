"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { Pencil, Plus, Trash2, Plug } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type {
  TenantIntegration,
  IntegrationCategory,
  IntegrationStatus,
} from "../types";
import {
  useTenantIntegrations,
  useCreateTenantIntegration,
  useUpdateTenantIntegration,
  useDeleteTenantIntegration,
} from "../hooks/use-integrations";

// ── Zod schema ───────────────────────────────────────────────

const integrationSchema = z.object({
  name: z.string().min(1, "Name is required"),
  category: z.enum(["crm", "calendar", "messaging", "email", "custom_webhook"]),
  provider: z.string().min(1, "Provider is required"),
  status: z.enum(["active", "inactive", "error"]).optional(),
  credentials: z
    .string()
    .optional()
    .refine(
      (val) => {
        if (!val || val.trim() === "") return true;
        try {
          JSON.parse(val);
          return true;
        } catch {
          return false;
        }
      },
      { message: "Must be valid JSON" }
    ),
  config: z
    .string()
    .optional()
    .refine(
      (val) => {
        if (!val || val.trim() === "") return true;
        try {
          JSON.parse(val);
          return true;
        } catch {
          return false;
        }
      },
      { message: "Must be valid JSON" }
    ),
});

type IntegrationFormValues = z.infer<typeof integrationSchema>;

// ── Category / status options ────────────────────────────────

const CATEGORY_OPTIONS: { value: IntegrationCategory; label: string }[] = [
  { value: "crm", label: "CRM" },
  { value: "calendar", label: "Calendar" },
  { value: "messaging", label: "Messaging" },
  { value: "email", label: "Email" },
  { value: "custom_webhook", label: "Custom Webhook" },
];

const STATUS_OPTIONS: { value: IntegrationStatus; label: string }[] = [
  { value: "active", label: "Active" },
  { value: "inactive", label: "Inactive" },
  { value: "error", label: "Error" },
];

// ── Helpers ──────────────────────────────────────────────────

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function statusVariant(
  status: IntegrationStatus
): "default" | "secondary" | "destructive" {
  if (status === "active") return "default";
  if (status === "inactive") return "secondary";
  return "destructive";
}

// ── IntegrationFormDialog ────────────────────────────────────

interface IntegrationFormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  integration?: TenantIntegration;
}

function IntegrationFormDialog({
  open,
  onOpenChange,
  integration,
}: IntegrationFormDialogProps) {
  const isEdit = !!integration;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<IntegrationFormValues>({
    resolver: zodResolver(integrationSchema),
    defaultValues: integration
      ? {
        name: integration.name,
        category: integration.category,
        provider: integration.provider,
        status: integration.status,
        credentials: "",
        config: integration.config
          ? JSON.stringify(integration.config, null, 2)
          : "",
      }
      : { category: "crm", status: "active", credentials: "", config: "" },
  });

  const createMutation = useCreateTenantIntegration();
  const updateMutation = useUpdateTenantIntegration(integration?.id ?? "");
  const mutation = isEdit ? updateMutation : createMutation;

  function handleClose(value: boolean) {
    if (!value) {
      reset();
      mutation.reset();
    }
    onOpenChange(value);
  }

  async function onSubmit(values: IntegrationFormValues) {
    const payload = {
      ...values,
      credentials: values.credentials?.trim()
        ? JSON.parse(values.credentials)
        : undefined,
      config: values.config?.trim()
        ? JSON.parse(values.config)
        : undefined,
    };
    await mutation.mutateAsync(payload);
    handleClose(false);
  }

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? "Edit Integration" : "Add Integration"}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? "Update the integration details below."
              : "Fill in the details to add a new integration."}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 pt-2">
          {/* Name */}
          <div className="space-y-1">
            <Label htmlFor="int-name">Name</Label>
            <Input
              id="int-name"
              placeholder="e.g. Zoho CRM Production"
              {...register("name")}
            />
            {errors.name && (
              <p className="text-xs text-destructive">{errors.name.message}</p>
            )}
          </div>

          {/* Category */}
          <div className="space-y-1">
            <Label htmlFor="int-category">Category</Label>
            <select
              id="int-category"
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              {...register("category")}
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            {errors.category && (
              <p className="text-xs text-destructive">
                {errors.category.message}
              </p>
            )}
          </div>

          {/* Provider */}
          <div className="space-y-1">
            <Label htmlFor="int-provider">Provider</Label>
            <Input
              id="int-provider"
              placeholder="e.g. zoho, twilio, hubspot"
              {...register("provider")}
            />
            {errors.provider && (
              <p className="text-xs text-destructive">
                {errors.provider.message}
              </p>
            )}
          </div>

          {/* Status (edit only) */}
          {isEdit && (
            <div className="space-y-1">
              <Label htmlFor="int-status">Status</Label>
              <select
                id="int-status"
                className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                {...register("status")}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Credentials (JSON) */}
          <div className="space-y-1">
            <Label htmlFor="int-credentials">Credentials (JSON)</Label>
            <Textarea
              id="int-credentials"
              placeholder='{"api_key": "...", "api_secret": "..."}'
              rows={3}
              className="font-mono text-xs"
              {...register("credentials")}
            />
            <p className="text-xs text-muted-foreground">
              Encrypted at rest. Leave empty to keep unchanged.
            </p>
            {errors.credentials && (
              <p className="text-xs text-destructive">
                {errors.credentials.message}
              </p>
            )}
          </div>

          {/* Configuration (JSON) */}
          <div className="space-y-1">
            <Label htmlFor="int-config">Configuration (JSON)</Label>
            <Textarea
              id="int-config"
              placeholder='{"webhook_url": "https://...", "sync_interval": 300}'
              rows={3}
              className="font-mono text-xs"
              {...register("config")}
            />
            {errors.config && (
              <p className="text-xs text-destructive">
                {errors.config.message}
              </p>
            )}
          </div>

          {/* API error */}
          {mutation.error && (
            <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {mutation.error.message}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => handleClose(false)}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting || mutation.isPending}>
              {mutation.isPending
                ? isEdit
                  ? "Saving…"
                  : "Adding…"
                : isEdit
                  ? "Save Changes"
                  : "Add Integration"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── IntegrationSettingsPage ──────────────────────────────────

export default function IntegrationSettingsPage() {
  const params = useParams<{ tenantId: string }>();
  const tenantId = params?.tenantId;

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingIntegration, setEditingIntegration] = useState<
    TenantIntegration | undefined
  >(undefined);

  const { data, isLoading } = useTenantIntegrations(tenantId);
  const deleteMutation = useDeleteTenantIntegration();

  const integrations = data?.integrations ?? [];

  function handleEdit(integration: TenantIntegration) {
    setEditingIntegration(integration);
    setDialogOpen(true);
  }

  function handleAdd() {
    setEditingIntegration(undefined);
    setDialogOpen(true);
  }

  function handleDelete(integration: TenantIntegration) {
    if (
      !confirm(
        `Delete integration "${integration.name}"? This action cannot be undone.`
      )
    ) {
      return;
    }
    deleteMutation.mutate({ id: integration.id });
  }

  const columns: ColumnDef<TenantIntegration>[] = [
    {
      accessorKey: "name",
      header: "Name",
      cell: ({ row }) => (
        <span className="font-medium">{row.original.name}</span>
      ),
    },
    {
      accessorKey: "category",
      header: "Category",
      cell: ({ row }) => (
        <Badge variant="outline" className="capitalize">
          {row.original.category}
        </Badge>
      ),
    },
    {
      accessorKey: "provider",
      header: "Provider",
      cell: ({ row }) => (
        <span className="capitalize">{row.original.provider}</span>
      ),
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => (
        <Badge variant={statusVariant(row.original.status)} className="capitalize">
          {row.original.status}
        </Badge>
      ),
    },
    {
      accessorKey: "last_synced_at",
      header: "Last Synced",
      cell: ({ row }) => (
        <span className="text-muted-foreground text-sm">
          {formatDate(row.original.last_synced_at)}
        </span>
      ),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <div className="flex items-center justify-end gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => handleEdit(row.original)}
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-destructive hover:text-destructive"
            onClick={() => handleDelete(row.original)}
            disabled={deleteMutation.isPending}
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ),
    },
  ];

  const table = useReactTable({
    data: integrations,
    columns,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Integrations</h2>
          <p className="text-sm text-muted-foreground">
            Manage third-party integrations for this tenant.
          </p>
        </div>
        <Button onClick={handleAdd} size="sm">
          <Plus className="mr-2 h-4 w-4" />
          Add Integration
        </Button>
      </div>

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((header) => (
                  <TableHead key={header.id}>
                    {header.isPlaceholder
                      ? null
                      : flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-24 text-center text-muted-foreground"
                >
                  Loading integrations…
                </TableCell>
              </TableRow>
            ) : table.getRowModel().rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={columns.length}
                  className="h-32 text-center"
                >
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Plug className="h-8 w-8 opacity-40" />
                    <p className="text-sm">No integrations configured.</p>
                    <p className="text-xs">
                      Click &ldquo;Add Integration&rdquo; to get started.
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
                        cell.getContext()
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Dialog */}
      <IntegrationFormDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        integration={editingIntegration}
      />
    </div>
  );
}
