"use client";

/**
 * EmailCard — integration card for SendGrid email sending.
 *
 * Allows configuring a SendGrid API key and default "from" address.
 * Stores credentials in the TenantIntegration table via the generic CRUD hooks.
 */

import { useState } from "react";
import {
    AlertCircle,
    CheckCircle2,
    Eye,
    EyeOff,
    Loader2,
    Mail,
    Save,
    Trash2,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";

import {
    useCreateTenantIntegration,
    useUpdateTenantIntegration,
    useDeleteTenantIntegration,
} from "../hooks/use-integrations";
import type { TenantIntegration } from "../types";

interface EmailCardProps {
    integration?: TenantIntegration;
    tenantId?: string;
}

export function EmailCard({ integration, tenantId }: EmailCardProps) {
    const [showKey, setShowKey] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);

    const [apiKey, setApiKey] = useState("");
    const [fromEmail, setFromEmail] = useState(
        (integration?.config?.default_from_email as string) ?? ""
    );
    const [fromName, setFromName] = useState(
        (integration?.config?.default_from_name as string) ?? ""
    );

    const createIntegration = useCreateTenantIntegration();
    const updateIntegration = useUpdateTenantIntegration(integration?.id ?? "");
    const deleteIntegration = useDeleteTenantIntegration();

    const isConnected = integration?.status === "active";
    const isSaving = createIntegration.isPending || updateIntegration.isPending;

    function handleSave() {
        if (!apiKey && !integration) return;

        const config: Record<string, unknown> = {
            default_from_email: fromEmail,
            default_from_name: fromName,
        };

        if (integration) {
            const body: Record<string, unknown> = { config };
            if (apiKey) {
                body.credentials = { api_key: apiKey };
            }
            body.status = "active";
            updateIntegration.mutate(body as Parameters<typeof updateIntegration.mutate>[0], {
                onSuccess: () => setApiKey(""),
            });
        } else {
            createIntegration.mutate(
                {
                    name: "SendGrid",
                    category: "email",
                    provider: "sendgrid",
                    status: "active",
                    credentials: { api_key: apiKey },
                    config,
                },
                { onSuccess: () => setApiKey("") }
            );
        }
    }

    function handleDelete() {
        if (!integration) return;
        deleteIntegration.mutate({ id: integration.id });
        setConfirmDelete(false);
    }

    const hasRequiredFields = fromEmail.trim().length > 0 && (integration || apiKey.trim().length > 0);

    return (
        <>
            <Card className="w-full">
                <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 pb-3">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-violet-600 text-white">
                            <Mail className="h-5 w-5" />
                        </div>
                        <div>
                            <CardTitle className="text-base">Email (SendGrid)</CardTitle>
                            <CardDescription className="text-xs">
                                Send emails to callers during or after calls
                            </CardDescription>
                        </div>
                    </div>

                    {isConnected ? (
                        <Badge variant="default" className="gap-1 bg-green-600 hover:bg-green-600">
                            <CheckCircle2 className="h-3 w-3" />
                            Connected
                        </Badge>
                    ) : (
                        <Badge variant="secondary" className="gap-1">
                            Not connected
                        </Badge>
                    )}
                </CardHeader>

                <CardContent className="space-y-4">
                    <div className="space-y-3">
                        <div className="space-y-1.5">
                            <Label className="text-xs">SendGrid API Key</Label>
                            <div className="relative">
                                <Input
                                    type={showKey ? "text" : "password"}
                                    placeholder={integration ? "••••••••• (update to change)" : "SG.xxxxxxxx..."}
                                    value={apiKey}
                                    onChange={(e) => setApiKey(e.target.value)}
                                    className="pr-10 text-xs"
                                />
                                <button
                                    type="button"
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                    onClick={() => setShowKey(!showKey)}
                                >
                                    {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <Label className="text-xs">Default From Email</Label>
                            <Input
                                type="email"
                                placeholder="noreply@yourcompany.com"
                                value={fromEmail}
                                onChange={(e) => setFromEmail(e.target.value)}
                                className="text-xs"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label className="text-xs">From Name (optional)</Label>
                            <Input
                                placeholder="e.g. Your Company Name"
                                value={fromName}
                                onChange={(e) => setFromName(e.target.value)}
                                className="text-xs"
                            />
                        </div>
                    </div>

                    {/* Error display */}
                    {(createIntegration.error || updateIntegration.error) && (
                        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-3 py-2 text-sm text-destructive flex items-center gap-2">
                            <AlertCircle className="h-4 w-4 shrink-0" />
                            {createIntegration.error?.message || updateIntegration.error?.message}
                        </div>
                    )}

                    <div className="flex items-center gap-2">
                        <Button
                            size="sm"
                            onClick={handleSave}
                            disabled={isSaving || !hasRequiredFields}
                            className="gap-1"
                        >
                            {isSaving ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                                <Save className="h-4 w-4" />
                            )}
                            {integration ? "Update" : "Save"}
                        </Button>

                        {integration && (
                            <Button
                                size="sm"
                                variant="ghost"
                                className="gap-1 text-destructive hover:text-destructive"
                                onClick={() => setConfirmDelete(true)}
                            >
                                <Trash2 className="h-4 w-4" />
                                Remove
                            </Button>
                        )}
                    </div>
                </CardContent>
            </Card>

            <AlertDialog open={confirmDelete} onOpenChange={setConfirmDelete}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>Remove Email Integration?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Agents will no longer be able to send emails during calls.
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction
                            onClick={handleDelete}
                            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                        >
                            Remove
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    );
}
