"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { CampaignWizardData } from "../../types";

export interface StepCallSettingsProps {
    data: CampaignWizardData;
    onUpdate: (partial: Partial<CampaignWizardData>) => void;
}

export function StepCallSettings({ data, onUpdate }: StepCallSettingsProps) {
    return (
        <div className="space-y-6">
            <div>
                <h2 className="text-lg font-semibold">Call Settings</h2>
                <p className="text-sm text-muted-foreground">
                    Configure campaign name, concurrency, and retry behavior.
                </p>
            </div>

            {/* Campaign name */}
            <div className="space-y-1.5">
                <Label htmlFor="campaign-name">
                    Campaign Name <span className="text-destructive">*</span>
                </Label>
                <Input
                    id="campaign-name"
                    placeholder="Q1 Follow-up Calls"
                    value={data.name}
                    onChange={(e) => onUpdate({ name: e.target.value })}
                />
            </div>

            {/* Description */}
            <div className="space-y-1.5">
                <Label htmlFor="campaign-desc">Description</Label>
                <Textarea
                    id="campaign-desc"
                    placeholder="Optional description for this campaign"
                    rows={2}
                    value={data.description}
                    onChange={(e) => onUpdate({ description: e.target.value })}
                />
            </div>

            {/* From number */}
            <div className="space-y-1.5">
                <Label htmlFor="from-number">From Phone Number</Label>
                <Input
                    id="from-number"
                    placeholder="+1234567890"
                    value={data.from_number}
                    onChange={(e) => onUpdate({ from_number: e.target.value })}
                />
                <p className="text-xs text-muted-foreground">
                    Leave blank to use the default outbound number.
                </p>
            </div>

            {/* Concurrency controls */}
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label>
                        Max Concurrent Calls:{" "}
                        <span className="font-mono">{data.max_concurrent}</span>
                    </Label>
                    <Slider
                        value={[data.max_concurrent]}
                        onValueChange={([v]) => onUpdate({ max_concurrent: v })}
                        min={1}
                        max={50}
                        step={1}
                    />
                    <p className="text-xs text-muted-foreground">1-50</p>
                </div>
                <div className="space-y-1.5">
                    <Label>
                        Calls per Minute:{" "}
                        <span className="font-mono">{data.calls_per_minute}</span>
                    </Label>
                    <Slider
                        value={[data.calls_per_minute]}
                        onValueChange={([v]) =>
                            onUpdate({ calls_per_minute: v })
                        }
                        min={1}
                        max={60}
                        step={1}
                    />
                    <p className="text-xs text-muted-foreground">1-60</p>
                </div>
            </div>

            {/* Retry settings */}
            <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                    <Label htmlFor="max-retries">Max Retries</Label>
                    <Input
                        id="max-retries"
                        type="number"
                        min={0}
                        max={10}
                        value={data.max_retries}
                        onChange={(e) =>
                            onUpdate({ max_retries: Number(e.target.value) })
                        }
                    />
                </div>
                <div className="space-y-1.5">
                    <Label htmlFor="retry-delay">Retry Delay (minutes)</Label>
                    <Input
                        id="retry-delay"
                        type="number"
                        min={1}
                        max={1440}
                        value={data.retry_delay_minutes}
                        onChange={(e) =>
                            onUpdate({
                                retry_delay_minutes: Number(e.target.value),
                            })
                        }
                    />
                </div>
            </div>

            {/* Schedule */}
            <div className="space-y-3 rounded-md border p-4">
                <div className="flex items-center justify-between">
                    <div>
                        <Label>Schedule for later</Label>
                        <p className="text-xs text-muted-foreground">
                            Start the campaign at a specific date and time instead of immediately.
                        </p>
                    </div>
                    <Switch
                        checked={!!data.scheduled_at}
                        onCheckedChange={(checked) =>
                            onUpdate({ scheduled_at: checked ? new Date(Date.now() + 3600_000).toISOString().slice(0, 16) : null })
                        }
                    />
                </div>
                {data.scheduled_at && (
                    <div className="space-y-1.5">
                        <Label htmlFor="scheduled-at">Start Date & Time</Label>
                        <Input
                            id="scheduled-at"
                            type="datetime-local"
                            value={data.scheduled_at.slice(0, 16)}
                            min={new Date().toISOString().slice(0, 16)}
                            onChange={(e) =>
                                onUpdate({
                                    scheduled_at: e.target.value
                                        ? new Date(e.target.value).toISOString()
                                        : null,
                                })
                            }
                        />
                    </div>
                )}
            </div>
        </div>
    );
}
