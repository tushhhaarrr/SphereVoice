"use client";

/**
 * Create Knowledge Base dialog.
 *
 * Simple form with name, description, sharing scope, and defaults.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";

import { useCreateKnowledgeBase } from "../hooks/use-knowledge-base";
import type { KnowledgeBaseCreateRequest, SharingScope } from "../types";

interface Props {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    tenantId?: string;
    tenantName?: string;
}

export function CreateKBDialog({ open, onOpenChange, tenantId, tenantName }: Props) {
    const createMutation = useCreateKnowledgeBase();
    const workspaceMode = Boolean(tenantId);
    const [scope, setScope] = useState<SharingScope>(workspaceMode ? "tenant" : "tenant");

    const {
        register,
        handleSubmit,
        reset,
        formState: { errors },
    } = useForm<KnowledgeBaseCreateRequest>({
        defaultValues: {
            name: "",
            description: "",
            sharing_scope: "tenant",
        },
    });

    const onSubmit = async (data: KnowledgeBaseCreateRequest) => {
        try {
            await createMutation.mutateAsync({
                ...data,
                tenant_id: tenantId,
                sharing_scope: workspaceMode ? "tenant" : scope,
            });
            reset();
            setScope("tenant");
            onOpenChange(false);
        } catch {
            // Error handled by mutation
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[480px]">
                <DialogHeader>
                    <DialogTitle>Create Knowledge Base</DialogTitle>
                    <DialogDescription>
                        {workspaceMode
                            ? `Create a tenant-scoped knowledge base for ${tenantName ?? "this workspace"}.`
                            : "Create a new document collection for your AI agents to reference during calls."}
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
                    <div className="space-y-2">
                        <Label htmlFor="name">Name</Label>
                        <Input
                            id="name"
                            placeholder="e.g. Product FAQ"
                            {...register("name", { required: "Name is required" })}
                        />
                        {errors.name && (
                            <p className="text-sm text-destructive">{errors.name.message}</p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="description">Description</Label>
                        <Textarea
                            id="description"
                            placeholder="What kind of documents will this contain?"
                            rows={3}
                            {...register("description")}
                        />
                    </div>

                    {workspaceMode ? (
                        <div className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
                            This knowledge base will be created as <strong className="font-medium text-foreground">tenant</strong>
                            {" "}scope for {tenantName ?? "the current workspace"}.
                        </div>
                    ) : (
                        <div className="space-y-2">
                            <Label>Sharing Scope</Label>
                            <Select
                                value={scope}
                                onValueChange={(v) => setScope(v as SharingScope)}
                            >
                                <SelectTrigger>
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="private">Private — Only you</SelectItem>
                                    <SelectItem value="tenant">Tenant — Same organization</SelectItem>
                                    <SelectItem value="global">Global — All tenants</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    )}

                    <DialogFooter>
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={createMutation.isPending}>
                            {createMutation.isPending ? "Creating..." : "Create"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
