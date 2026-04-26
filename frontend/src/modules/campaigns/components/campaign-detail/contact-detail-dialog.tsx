"use client";

import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { useCampaignContact } from "../../hooks/use-campaigns";
import {
  getContactStatusColor,
  getWritebackStatusColor,
  formatPhoneNumber,
  formatDateTime,
  getContactStatusLabel,
} from "../../lib/campaign-utils";

interface ContactDetailDialogProps {
  campaignId: string;
  tenantId?: string;
  contactId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ContactDetailDialog({
  campaignId,
  tenantId,
  contactId,
  open,
  onOpenChange,
}: ContactDetailDialogProps) {
  const contact = useCampaignContact(campaignId, contactId ?? "", tenantId);

  const c = contact.data;
  const statusColor = c ? getContactStatusColor(c.status) : null;
  const wbColor = c?.writeback_status
    ? getWritebackStatusColor(c.writeback_status)
    : null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Contact Details</DialogTitle>
        </DialogHeader>

        {contact.isLoading && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Loading…
          </p>
        )}

        {contact.isError && (
          <p className="py-8 text-center text-sm text-red-600">
            Failed to load contact.
          </p>
        )}

        {c && statusColor && (
          <ScrollArea className="max-h-[60vh]">
            <div className="space-y-4 pr-4">
              {/* Header */}
              <div className="flex items-center justify-between">
                <span className="text-lg font-semibold tabular-nums">
                  {formatPhoneNumber(c.phone_number)}
                </span>
                <Badge className={`${statusColor.bg} ${statusColor.text} border-0`}>
                  <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full ${statusColor.dot}`} />
                  {getContactStatusLabel(c.status)}
                </Badge>
              </div>

              <Separator />

              {/* Metadata */}
              <div className="grid grid-cols-2 gap-y-2 text-sm">
                <span className="text-muted-foreground">CRM Record ID</span>
                <span className="font-mono text-xs">{c.crm_record_id ?? "—"}</span>

                <span className="text-muted-foreground">CRM Module</span>
                <span>{c.crm_module ?? "—"}</span>

                <span className="text-muted-foreground">Attempts</span>
                <span>{c.attempt_count} / {c.max_attempts}</span>

                <span className="text-muted-foreground">Next Retry</span>
                <span>{formatDateTime(c.next_retry_at)}</span>

                <span className="text-muted-foreground">Call ID</span>
                <span className="font-mono text-xs">{c.call_id ?? "—"}</span>

                <span className="text-muted-foreground">Priority</span>
                <span>{c.priority}</span>

                <span className="text-muted-foreground">Created</span>
                <span>{formatDateTime(c.created_at)}</span>

                <span className="text-muted-foreground">Updated</span>
                <span>{formatDateTime(c.updated_at)}</span>
              </div>

              {/* Failure reason — prominent when status is failed */}
              {["failed", "no_answer", "busy", "voicemail"].includes(c.status) && (
                <>
                  <Separator />
                  <div className="rounded-md border border-destructive/20 bg-destructive/5 p-3 space-y-2">
                    <p className="text-sm font-medium text-destructive">
                      Call {c.status === "failed" ? "Failed" : c.status === "no_answer" ? "No Answer" : c.status === "busy" ? "Busy" : "Voicemail"}
                    </p>
                    <div className="grid grid-cols-2 gap-y-1 text-xs">
                      <span className="text-muted-foreground">Attempts made</span>
                      <span>{c.attempt_count} of {c.max_attempts}</span>
                      <span className="text-muted-foreground">Last attempt</span>
                      <span>{formatDateTime(c.updated_at)}</span>
                      {c.next_retry_at && (
                        <>
                          <span className="text-muted-foreground">Next retry</span>
                          <span>{formatDateTime(c.next_retry_at)}</span>
                        </>
                      )}
                      {c.attempt_count >= c.max_attempts && (
                        <>
                          <span className="col-span-2 mt-1 text-amber-600 dark:text-amber-400">
                            Max attempts reached — use &quot;Retry All Failed&quot; to reset
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </>
              )}

              {/* Writeback Status */}
              {c.writeback_status && wbColor && (
                <>
                  <Separator />
                  <div className="space-y-1">
                    <span className="text-sm font-medium">Writeback Status</span>
                    <div className="flex items-center gap-2">
                      <Badge className={`${wbColor.bg} ${wbColor.text} border-0`}>
                        {c.writeback_status}
                      </Badge>
                      {c.writeback_error && (
                        <span className="text-xs text-red-600">{c.writeback_error}</span>
                      )}
                    </div>
                  </div>
                </>
              )}

              {/* Contact Data */}
              {Object.keys(c.contact_data).length > 0 && (
                <>
                  <Separator />
                  <div className="space-y-1">
                    <span className="text-sm font-medium">Contact Data</span>
                    <pre className="rounded-md bg-muted p-3 text-xs overflow-x-auto">
                      {JSON.stringify(c.contact_data, null, 2)}
                    </pre>
                  </div>
                </>
              )}

              {/* Extracted Data */}
              {Object.keys(c.extracted_data).length > 0 && (
                <>
                  <Separator />
                  <div className="space-y-1">
                    <span className="text-sm font-medium">Extracted Data</span>
                    <pre className="rounded-md bg-muted p-3 text-xs overflow-x-auto">
                      {JSON.stringify(c.extracted_data, null, 2)}
                    </pre>
                  </div>
                </>
              )}

              {/* Tool Results */}
              {c.tool_results.length > 0 && (
                <>
                  <Separator />
                  <div className="space-y-1">
                    <span className="text-sm font-medium">
                      Tool Results ({c.tool_results.length})
                    </span>
                    {c.tool_results.map((result, idx) => (
                      <pre
                        key={idx}
                        className="rounded-md bg-muted p-3 text-xs overflow-x-auto"
                      >
                        {JSON.stringify(result, null, 2)}
                      </pre>
                    ))}
                  </div>
                </>
              )}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  );
}
