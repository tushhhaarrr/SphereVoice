"use client";

import { useState } from "react";
import { Eye, Loader2, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { usePreviewContacts } from "../../hooks/use-campaigns";

interface ContactPreviewProps {
    campaignId: string;
    tenantId?: string;
    disabled?: boolean;
}

export function ContactPreview({ campaignId, tenantId, disabled }: ContactPreviewProps) {
    const [open, setOpen] = useState(false);
    const preview = usePreviewContacts(campaignId, tenantId);

    const handleOpen = () => {
        setOpen(true);
        preview.mutate();
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button
                    variant="outline"
                    size="sm"
                    onClick={handleOpen}
                    disabled={disabled}
                >
                    <Eye className="mr-1 h-4 w-4" />
                    Preview Contacts
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Users className="h-5 w-5" />
                        Contact Preview
                    </DialogTitle>
                </DialogHeader>

                {preview.isPending && (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    </div>
                )}

                {preview.isError && (
                    <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                        {preview.error.message}
                    </div>
                )}

                {preview.data && (
                    <div className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Showing first {preview.data.contacts.length} of{" "}
                            <strong>{preview.data.total}</strong> contacts from CRM.
                        </p>

                        <div className="overflow-x-auto rounded-md border">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b bg-muted/50">
                                        <th className="px-3 py-2 text-left font-medium">Name</th>
                                        <th className="px-3 py-2 text-left font-medium">Phone</th>
                                        <th className="px-3 py-2 text-left font-medium">Email</th>
                                        <th className="px-3 py-2 text-left font-medium">Company</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {preview.data.contacts.map((c) => (
                                        <tr
                                            key={c.crm_id || c.phone}
                                            className="border-b last:border-0"
                                        >
                                            <td className="px-3 py-2">{c.name || "—"}</td>
                                            <td className="px-3 py-2 font-mono text-xs">
                                                {c.phone || "—"}
                                            </td>
                                            <td className="px-3 py-2 text-xs">
                                                {c.email || "—"}
                                            </td>
                                            <td className="px-3 py-2 text-xs">
                                                {c.company || "—"}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
