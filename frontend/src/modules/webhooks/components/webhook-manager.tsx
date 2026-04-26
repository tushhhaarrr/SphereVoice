"use client";

/**
 * Webhook Manager — create, list, toggle, delete webhooks + view deliveries.
 */

import {
    Globe,
    Plus,
    RefreshCw,
    Trash2,
} from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";

import {
    useCreateWebhook,
    useDeleteWebhook,
    useUpdateWebhook,
    useWebhooks,
    WEBHOOK_EVENT_TYPES,
    type Webhook,
    type WebhookCreateRequest,
} from "@/modules/webhooks";
import { WebhookDeliveryLog } from "./webhook-delivery-log";

// ── Component ───────────────────────────────────────────────

export function WebhookManager() {
    const { data, isLoading } = useWebhooks({ limit: 50 });
    const [selectedWebhookId, setSelectedWebhookId] = useState<string | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);

    const webhooks = data?.webhooks ?? [];

    return (
        <div className="flex flex-col gap-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-lg font-semibold">Webhooks</h2>
                    <p className="text-sm text-muted-foreground">
                        Receive real-time notifications when events occur
                    </p>
                </div>
                <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
                    <DialogTrigger asChild>
                        <Button>
                            <Plus className="mr-1 h-4 w-4" />
                            Add Webhook
                        </Button>
                    </DialogTrigger>
                    <CreateWebhookDialog onClose={() => setDialogOpen(false)} />
                </Dialog>
            </div>

            <Separator />

            {/* Webhook table */}
            {isLoading ? (
                <div className="flex items-center justify-center py-12">
                    <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
            ) : webhooks.length === 0 ? (
                <Card>
                    <CardContent className="flex flex-col items-center justify-center py-12">
                        <Globe className="mb-3 h-12 w-12 text-muted-foreground/30" />
                        <p className="text-sm text-muted-foreground">No webhooks configured</p>
                        <p className="mt-1 text-xs text-muted-foreground/60">
                            Add a webhook to receive event notifications
                        </p>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>URL</TableHead>
                                <TableHead>Events</TableHead>
                                <TableHead>Active</TableHead>
                                <TableHead className="w-[120px]" />
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {webhooks.map((wh) => (
                                <WebhookRow
                                    key={wh.id}
                                    webhook={wh}
                                    isSelected={selectedWebhookId === wh.id}
                                    onSelect={() =>
                                        setSelectedWebhookId(
                                            selectedWebhookId === wh.id ? null : wh.id,
                                        )
                                    }
                                />
                            ))}
                        </TableBody>
                    </Table>
                </Card>
            )}

            {/* Delivery log for selected webhook */}
            {selectedWebhookId && (
                <WebhookDeliveryLog webhookId={selectedWebhookId} />
            )}
        </div>
    );
}

// ── Webhook Row ─────────────────────────────────────────────

function WebhookRow({
    webhook,
    isSelected,
    onSelect,
}: {
    webhook: Webhook;
    isSelected: boolean;
    onSelect: () => void;
}) {
    const updateWebhook = useUpdateWebhook();
    const deleteWebhook = useDeleteWebhook();

    const toggleActive = () => {
        updateWebhook.mutate({
            id: webhook.id,
            data: { is_active: !webhook.is_active },
        });
    };

    return (
        <TableRow
            className={isSelected ? "bg-muted/50" : "cursor-pointer hover:bg-muted/30"}
            onClick={onSelect}
        >
            <TableCell className="max-w-[300px] truncate font-mono text-xs">
                {webhook.url}
            </TableCell>
            <TableCell>
                <div className="flex flex-wrap gap-1">
                    {webhook.events.map((e) => (
                        <Badge key={e} variant="outline" className="text-[10px]">
                            {e}
                        </Badge>
                    ))}
                </div>
            </TableCell>
            <TableCell>
                <Switch
                    checked={webhook.is_active}
                    onCheckedChange={toggleActive}
                    onClick={(e) => e.stopPropagation()}
                />
            </TableCell>
            <TableCell>
                <AlertDialog>
                    <AlertDialogTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="text-destructive"
                            onClick={(e) => e.stopPropagation()}
                        >
                            <Trash2 className="h-4 w-4" />
                        </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                        <AlertDialogHeader>
                            <AlertDialogTitle>Delete this webhook?</AlertDialogTitle>
                            <AlertDialogDescription>
                                This will permanently delete the webhook and all its delivery
                                history. This action cannot be undone.
                            </AlertDialogDescription>
                        </AlertDialogHeader>
                        <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                                onClick={() => deleteWebhook.mutate(webhook.id)}
                            >
                                Delete
                            </AlertDialogAction>
                        </AlertDialogFooter>
                    </AlertDialogContent>
                </AlertDialog>
            </TableCell>
        </TableRow>
    );
}

// ── Create Webhook Dialog ──────────────────────────────────

interface FormValues {
    url: string;
    secret: string;
}

function CreateWebhookDialog({ onClose }: { onClose: () => void }) {
    const createWebhook = useCreateWebhook();
    const {
        register,
        handleSubmit,
        formState: { errors },
    } = useForm<FormValues>();
    const [selectedEvents, setSelectedEvents] = useState<string[]>([
        "call_ended",
    ]);

    const toggleEvent = (event: string) => {
        setSelectedEvents((prev) =>
            prev.includes(event)
                ? prev.filter((e) => e !== event)
                : [...prev, event],
        );
    };

    const onSubmit = (values: FormValues) => {
        const payload: WebhookCreateRequest = {
            url: values.url,
            events: selectedEvents,
            secret: values.secret || undefined,
        };
        createWebhook.mutate(payload, {
            onSuccess: () => onClose(),
        });
    };

    return (
        <DialogContent className="sm:max-w-md">
            <DialogHeader>
                <DialogTitle>Add Webhook</DialogTitle>
                <DialogDescription>
                    We&apos;ll send POST requests to this URL when selected events occur.
                </DialogDescription>
            </DialogHeader>
            <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
                <div className="space-y-2">
                    <Label htmlFor="url">Endpoint URL</Label>
                    <Input
                        id="url"
                        placeholder="https://example.com/webhooks/SphereVoice"
                        {...register("url", {
                            required: "URL is required",
                            pattern: {
                                value: /^https?:\/\/.+/,
                                message: "Must be a valid HTTP(S) URL",
                            },
                        })}
                    />
                    {errors.url && (
                        <p className="text-xs text-destructive">{errors.url.message}</p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label>Events</Label>
                    <div className="flex flex-wrap gap-2">
                        {WEBHOOK_EVENT_TYPES.map((evt) => (
                            <Badge
                                key={evt}
                                variant={selectedEvents.includes(evt) ? "default" : "outline"}
                                className="cursor-pointer"
                                onClick={() => toggleEvent(evt)}
                            >
                                {evt}
                            </Badge>
                        ))}
                    </div>
                    {selectedEvents.length === 0 && (
                        <p className="text-xs text-destructive">
                            Select at least one event
                        </p>
                    )}
                </div>

                <div className="space-y-2">
                    <Label htmlFor="secret">Signing Secret (optional)</Label>
                    <Input
                        id="secret"
                        type="password"
                        placeholder="whsec_..."
                        {...register("secret")}
                    />
                    <p className="text-xs text-muted-foreground">
                        Used to sign payloads with HMAC-SHA256
                    </p>
                </div>

                <DialogFooter>
                    <Button
                        type="submit"
                        disabled={
                            createWebhook.isPending || selectedEvents.length === 0
                        }
                    >
                        {createWebhook.isPending ? "Creating..." : "Create Webhook"}
                    </Button>
                </DialogFooter>
            </form>
        </DialogContent>
    );
}
