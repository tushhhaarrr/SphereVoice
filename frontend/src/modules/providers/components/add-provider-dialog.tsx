"use client";

/**
 * Add Provider dialog.
 *
 * Form for creating a new provider key with category selection,
 * provider name, and API key input.
 */

import { useEffect, useMemo } from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
} from "@/components/ui/dialog";
import { useAuth } from "@/modules/auth";
import { useCreateProvider } from "../hooks/use-providers";
import type { ProviderCategory } from "../types";
import {
    CATEGORY_LABELS,
    PROVIDER_FAMILY_OPTIONS,
    RECOMMENDED_DEFAULTS,
    getProviderDescription,
    getProviderLabel,
    normalizeProviderName,
} from "../lib/catalog";

const CUSTOM_PROVIDER_VALUE = "__custom__";

const schema = z.object({
    category: z.enum(["stt", "llm", "tts", "telephony"]),
    provider_choice: z.string().min(1, "Provider is required"),
    custom_provider_name: z.string().optional(),
    api_key: z.string().min(1, "API key is required"),
    docs_url: z.union([z.literal(""), z.string().url("Enter a valid documentation URL")]).optional(),
    integration_notes: z.string().max(500, "Notes must be 500 characters or fewer").optional(),
    is_default: z.boolean().optional(),
}).superRefine((value, context) => {
    if (value.provider_choice === CUSTOM_PROVIDER_VALUE && !value.custom_provider_name?.trim()) {
        context.addIssue({
            code: z.ZodIssueCode.custom,
            path: ["custom_provider_name"],
            message: "Provider name is required",
        });
    }
});

type FormValues = z.infer<typeof schema>;

interface AddProviderDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    tenantId?: string;
    tenantName?: string;
}

export function AddProviderDialog({ open, onOpenChange, tenantId, tenantName }: AddProviderDialogProps) {
    const createMutation = useCreateProvider();
    const { isAdmin, canWrite } = useAuth();
    const supportsDefaultToggle = tenantId ? canWrite : isAdmin;

    const {
        register,
        handleSubmit,
        reset,
        control,
        formState: { errors, isSubmitting },
    } = useForm<FormValues>({
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        resolver: zodResolver(schema as any),
        defaultValues: {
            category: "stt",
            provider_choice: RECOMMENDED_DEFAULTS.stt,
            custom_provider_name: "",
            api_key: "",
            docs_url: "",
            integration_notes: "",
            is_default: supportsDefaultToggle,
        },
    });

    const selectedCategory = useWatch({
        control,
        name: "category",
    }) as ProviderCategory;
    const availableProviders = useMemo(
        () => [...(PROVIDER_FAMILY_OPTIONS[selectedCategory] || []), CUSTOM_PROVIDER_VALUE],
        [selectedCategory],
    );
    const selectedProviderChoice = useWatch({
        control,
        name: "provider_choice",
    });
    const customProviderName = useWatch({
        control,
        name: "custom_provider_name",
    });

    const isCustomProvider = selectedProviderChoice === CUSTOM_PROVIDER_VALUE;
    const selectedProviderName = isCustomProvider ? customProviderName?.trim() || "" : selectedProviderChoice;

    useEffect(() => {
        if (!selectedProviderChoice || availableProviders.includes(selectedProviderChoice)) {
            return;
        }

        reset({
            category: selectedCategory,
            provider_choice: RECOMMENDED_DEFAULTS[selectedCategory],
            custom_provider_name: "",
            api_key: "",
            docs_url: "",
            integration_notes: "",
            is_default: supportsDefaultToggle,
        });
    }, [availableProviders, reset, selectedCategory, selectedProviderChoice, supportsDefaultToggle]);

    async function onSubmit(data: FormValues) {
        try {
            const providerName = data.provider_choice === CUSTOM_PROVIDER_VALUE
                ? (data.custom_provider_name || "").trim()
                : data.provider_choice;
            const normalizedProviderName = data.provider_choice === CUSTOM_PROVIDER_VALUE
                ? providerName
                : normalizeProviderName(providerName, data.category);
            const config = {
                ...(data.provider_choice === CUSTOM_PROVIDER_VALUE ? { manual_provider: true } : {}),
                ...(data.docs_url?.trim() ? { documentation_url: data.docs_url.trim() } : {}),
                ...(data.integration_notes?.trim() ? { integration_notes: data.integration_notes.trim() } : {}),
            };

            await createMutation.mutateAsync({
                provider_name: normalizedProviderName,
                category: data.category,
                api_key: data.api_key,
                is_default: data.is_default,
                tenant_id: tenantId,
                config: Object.keys(config).length > 0 ? config : undefined,
            });
            reset({
                category: "stt",
                provider_choice: RECOMMENDED_DEFAULTS.stt,
                custom_provider_name: "",
                api_key: "",
                docs_url: "",
                integration_notes: "",
                is_default: supportsDefaultToggle,
            });
            onOpenChange(false);
        } catch {
            // Error is handled by TanStack Query
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>Add Provider</DialogTitle>
                    <DialogDescription>
                        {tenantId
                            ? `Add a workspace-scoped provider for ${tenantName ?? "this workspace"}. You can mark it as the default for this workspace.`
                            : "Add a shared provider. Models and voices are synced after saving so the agent editor can use the provider catalog directly."}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="category">Category</Label>
                        <select
                            id="category"
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            {...register("category")}
                        >
                            <option value="stt">{CATEGORY_LABELS.stt}</option>
                            <option value="llm">{CATEGORY_LABELS.llm}</option>
                            <option value="tts">{CATEGORY_LABELS.tts}</option>
                            <option value="telephony">{CATEGORY_LABELS.telephony}</option>
                        </select>
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="provider_name">Provider</Label>
                        <select
                            id="provider_name"
                            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                            {...register("provider_choice")}
                        >
                            {availableProviders.map((name) => (
                                <option key={name} value={name}>
                                    {name === CUSTOM_PROVIDER_VALUE ? "Custom / Manual provider" : getProviderLabel(name)}
                                </option>
                            ))}
                        </select>
                        {isCustomProvider ? (
                            <div className="space-y-2 rounded-md border border-dashed px-3 py-3">
                                <div className="space-y-2">
                                    <Label htmlFor="custom_provider_name">Provider name</Label>
                                    <Input
                                        id="custom_provider_name"
                                        placeholder="OpenRouter, Fireworks, Acme Voice, ..."
                                        autoComplete="off"
                                        {...register("custom_provider_name")}
                                    />
                                    {errors.custom_provider_name && (
                                        <p className="text-xs text-destructive">{errors.custom_provider_name.message}</p>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="docs_url">Documentation URL</Label>
                                    <Input
                                        id="docs_url"
                                        type="url"
                                        placeholder="https://docs.provider.com/api"
                                        autoComplete="off"
                                        {...register("docs_url")}
                                    />
                                    <p className="text-xs text-muted-foreground">
                                        Optional. Add the provider docs URL so the integration details are easy to trace when first-class support is added.
                                    </p>
                                    {errors.docs_url && (
                                        <p className="text-xs text-destructive">{errors.docs_url.message}</p>
                                    )}
                                </div>

                                <div className="space-y-2">
                                    <Label htmlFor="integration_notes">Integration notes</Label>
                                    <textarea
                                        id="integration_notes"
                                        rows={3}
                                        className="flex min-h-24 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                                        placeholder="Base URL, auth format, model family, setup quirks, ..."
                                        {...register("integration_notes")}
                                    />
                                    {errors.integration_notes && (
                                        <p className="text-xs text-destructive">{errors.integration_notes.message}</p>
                                    )}
                                </div>
                            </div>
                        ) : null}
                        {selectedProviderName ? (
                            <div className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
                                {isCustomProvider
                                    ? "Use this when the provider is not in the built-in catalog yet. The platform will store the credential now, show it in provider families, and you can add richer test or catalog support later."
                                    : getProviderDescription(selectedProviderName)}
                            </div>
                        ) : null}
                        {errors.provider_choice && (
                            <p className="text-xs text-destructive">{errors.provider_choice.message}</p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="api_key">Credential</Label>
                        <Input
                            id="api_key"
                            type="password"
                            placeholder={
                                selectedProviderName === "twilio"
                                    ? "account_sid:auth_token"
                                    : selectedProviderName === "vobiz"
                                        ? "auth_id:api_key"
                                        : "Enter credential..."
                            }
                            autoComplete="off"
                            {...register("api_key")}
                        />
                        <p className="text-xs text-muted-foreground">
                            The platform auto-syncs models and voices after save when catalog refresh is supported. Use Refresh later to re-sync metadata on demand.
                        </p>
                        {errors.api_key && (
                            <p className="text-xs text-destructive">{errors.api_key.message}</p>
                        )}
                    </div>

                    {supportsDefaultToggle ? (
                        <div className="flex items-center space-x-2">
                            <input
                                id="is_default"
                                type="checkbox"
                                className="h-4 w-4 rounded border-input"
                                {...register("is_default")}
                            />
                            <Label htmlFor="is_default" className="text-sm font-normal">
                                {tenantId
                                    ? "Set as the default provider for this workspace and category"
                                    : "Set as the shared default provider for this category"}
                            </Label>
                        </div>
                    ) : tenantId ? (
                        <div className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
                            This provider will be scoped to {tenantName ?? "the current tenant workspace"}.
                        </div>
                    ) : null}

                    {createMutation.error && (
                        <div className="rounded-md bg-destructive/10 px-3 py-2 text-sm text-destructive">
                            {createMutation.error.message}
                        </div>
                    )}

                    <div className="flex justify-end gap-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSubmitting || createMutation.isPending}>
                            {createMutation.isPending ? (
                                <>
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                    Adding...
                                </>
                            ) : (
                                "Add Provider"
                            )}
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    );
}
