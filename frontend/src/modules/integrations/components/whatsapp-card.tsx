"use client";

/**
 * WhatsAppCard — integration card for Meta WhatsApp Cloud API.
 *
 * Allows configuring Access Token, Phone Number ID, and Business Account ID.
 * Stores credentials in the TenantIntegration table via the generic CRUD hooks.
 */

import { useState } from "react";
import {
    AlertCircle,
    CheckCircle2,
    Eye,
    EyeOff,
    Loader2,
    MessageSquare,
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

interface WhatsAppCardProps {
    integration?: TenantIntegration;
    tenantId?: string;
}

export function WhatsAppCard({ integration, tenantId }: WhatsAppCardProps) {
    const [showToken, setShowToken] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState(false);

    const [accessToken, setAccessToken] = useState("");
    const [phoneNumberId, setPhoneNumberId] = useState(
        (integration?.config?.phone_number_id as string) ?? ""
    );
    const [businessAccountId, setBusinessAccountId] = useState(
        (integration?.config?.business_account_id as string) ?? ""
    );

    const createIntegration = useCreateTenantIntegration();
    const updateIntegration = useUpdateTenantIntegration(integration?.id ?? "");
    const deleteIntegration = useDeleteTenantIntegration();

    const isConnected = integration?.status === "active";
    const isSaving = createIntegration.isPending || updateIntegration.isPending;

    function handleSave() {
        if (!accessToken && !integration) return;

        const config: Record<string, unknown> = {
            phone_number_id: phoneNumberId,
            business_account_id: businessAccountId,
        };

        if (integration) {
            const body: Record<string, unknown> = { config };
            if (accessToken) {
                body.credentials = { access_token: accessToken };
            }
            body.status = "active";
            updateIntegration.mutate(body as Parameters<typeof updateIntegration.mutate>[0], {
                onSuccess: () => setAccessToken(""),
            });
        } else {
            createIntegration.mutate(
                {
                    name: "WhatsApp (Meta)",
                    category: "messaging",
                    provider: "whatsapp",
                    status: "active",
                    credentials: { access_token: accessToken },
                    config,
                },
                { onSuccess: () => setAccessToken("") }
            );
        }
    }

    function handleDelete() {
        if (!integration) return;
        deleteIntegration.mutate({ id: integration.id });
        setConfirmDelete(false);
    }

    const hasRequiredFields = phoneNumberId.trim().length > 0 && (integration || accessToken.trim().length > 0);

    return (
        <>
            <Card className="w-full">
                <CardHeader className="flex flex-row items-start justify-between gap-4 space-y-0 pb-3">
                    <div className="flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-emerald-600 text-white">
                            <MessageSquare className="h-5 w-5" />
                        </div>
                        <div>
                            <CardTitle className="text-base">WhatsApp</CardTitle>
                            <CardDescription className="text-xs">
                                Send WhatsApp messages to callers via Meta Cloud API
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
                            <Label className="text-xs">Access Token</Label>
                            <div className="relative">
                                <Input
                                    type={showToken ? "text" : "password"}
                                    placeholder={integration ? "••••••••• (update to change)" : "Meta API access token"}
                                    value={accessToken}
                                    onChange={(e) => setAccessToken(e.target.value)}
                                    className="pr-10 text-xs"
                                />
                                <button
                                    type="button"
                                    className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                                    onClick={() => setShowToken(!showToken)}
                                >
                                    {showToken ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                        </div>

                        <div className="space-y-1.5">
                            <Label className="text-xs">Phone Number ID</Label>
                            <Input
                                placeholder="e.g. 123456789012345"
                                value={phoneNumberId}
                                onChange={(e) => setPhoneNumberId(e.target.value)}
                                className="text-xs"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label className="text-xs">Business Account ID</Label>
                            <Input
                                placeholder="e.g. 987654321098765 (optional)"
                                value={businessAccountId}
                                onChange={(e) => setBusinessAccountId(e.target.value)}
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
                        <AlertDialogTitle>Remove WhatsApp Integration?</AlertDialogTitle>
                        <AlertDialogDescription>
                            Agents will no longer be able to send WhatsApp messages during calls.
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
