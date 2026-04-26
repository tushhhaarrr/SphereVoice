"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardFooter,
    CardHeader,
    CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import type { AgentTemplate, TemplateListResponse } from "../types";
import { useTemplateToAgent } from "../hooks/use-templates";

// We need the dialog imports - let me check what's available
// Using the existing shadcn dialog component

interface TemplateGalleryProps {
    data: TemplateListResponse | undefined;
    isLoading: boolean;
    tenantId?: string;
}

const CATEGORY_COLORS: Record<string, string> = {
    Healthcare: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200",
    "Real Estate": "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    "Customer Support": "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
    Retail: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    Education: "bg-pink-100 text-pink-800 dark:bg-pink-900 dark:text-pink-200",
    Sales: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
};

function getCategoryColor(category: string): string {
    return CATEGORY_COLORS[category] || "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200";
}

function TemplateCard({
    template,
    tenantId,
}: {
    template: AgentTemplate;
    tenantId?: string;
}) {
    const [open, setOpen] = useState(false);
    const [agentName, setAgentName] = useState(template.name);
    const [selectedTenant, setSelectedTenant] = useState(tenantId || "");
    const createAgent = useTemplateToAgent();

    const handleUseTemplate = () => {
        if (!selectedTenant || !agentName.trim()) return;
        createAgent.mutate(
            {
                templateId: template.id,
                data: { tenant_id: selectedTenant, name: agentName },
            },
            {
                onSuccess: () => {
                    setOpen(false);
                },
            }
        );
    };

    return (
        <Card className="flex flex-col">
            <CardHeader className="pb-3">
                <div className="flex items-start justify-between gap-2">
                    <CardTitle className="text-base leading-tight">
                        {template.name}
                    </CardTitle>
                    {template.is_builtin && (
                        <Badge variant="secondary" className="shrink-0 text-xs">
                            Built-in
                        </Badge>
                    )}
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                    <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getCategoryColor(template.category)}`}
                    >
                        {template.category}
                    </span>
                    {template.tags.slice(0, 3).map((tag) => (
                        <Badge key={tag} variant="outline" className="text-xs">
                            {tag}
                        </Badge>
                    ))}
                </div>
            </CardHeader>
            <CardContent className="flex-1">
                <CardDescription className="line-clamp-3 text-sm">
                    {template.description || "No description available."}
                </CardDescription>
                <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                    <span>Type: {template.agent_type === "single_prompt" ? "Single Prompt" : "Conversation Flow"}</span>
                    {template.llm_model && <span>LLM: {template.llm_model}</span>}
                    <span>Lang: {template.language}</span>
                </div>
            </CardContent>
            <CardFooter className="pt-3">
                <Dialog open={open} onOpenChange={setOpen}>
                    <DialogTrigger asChild>
                        <Button size="sm" className="w-full">
                            Use Template
                        </Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Create Agent from Template</DialogTitle>
                            <DialogDescription>
                                Create a new agent based on &quot;{template.name}&quot;
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 pt-2">
                            <div className="space-y-2">
                                <Label htmlFor="agent-name">Agent Name</Label>
                                <Input
                                    id="agent-name"
                                    value={agentName}
                                    onChange={(e) => setAgentName(e.target.value)}
                                    placeholder="My new agent..."
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="tenant-select">Tenant ID</Label>
                                <Input
                                    id="tenant-select"
                                    value={selectedTenant}
                                    onChange={(e) => setSelectedTenant(e.target.value)}
                                    placeholder="Enter tenant UUID"
                                />
                            </div>
                            <Button
                                onClick={handleUseTemplate}
                                disabled={createAgent.isPending || !selectedTenant || !agentName.trim()}
                                className="w-full"
                            >
                                {createAgent.isPending ? "Creating..." : "Create Agent"}
                            </Button>
                            {createAgent.isError && (
                                <p className="text-sm text-red-500">
                                    {createAgent.error.message}
                                </p>
                            )}
                        </div>
                    </DialogContent>
                </Dialog>
            </CardFooter>
        </Card>
    );
}

export function TemplateGallery({
    data,
    isLoading,
    tenantId,
}: TemplateGalleryProps) {
    const [categoryFilter, setCategoryFilter] = useState<string>("all");

    if (isLoading) {
        return (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 6 }).map((_, i) => (
                    <Card key={i}>
                        <CardHeader>
                            <div className="h-5 w-40 animate-pulse rounded bg-muted" />
                            <div className="h-3 w-20 animate-pulse rounded bg-muted mt-2" />
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-2">
                                <div className="h-3 w-full animate-pulse rounded bg-muted" />
                                <div className="h-3 w-3/4 animate-pulse rounded bg-muted" />
                            </div>
                        </CardContent>
                    </Card>
                ))}
            </div>
        );
    }

    if (!data || data.templates.length === 0) {
        return (
            <div className="flex h-40 items-center justify-center text-muted-foreground">
                No templates available.
            </div>
        );
    }

    const categories = [
        "all",
        ...Array.from(new Set(data.templates.map((t) => t.category))),
    ];
    const filtered =
        categoryFilter === "all"
            ? data.templates
            : data.templates.filter((t) => t.category === categoryFilter);

    return (
        <div className="space-y-4">
            <div className="flex items-center gap-3">
                <Label>Category</Label>
                <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                    <SelectTrigger className="w-[200px]">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {categories.map((cat) => (
                            <SelectItem key={cat} value={cat}>
                                {cat === "all" ? "All Categories" : cat}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <span className="text-sm text-muted-foreground">
                    {filtered.length} template{filtered.length !== 1 ? "s" : ""}
                </span>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filtered.map((template) => (
                    <TemplateCard
                        key={template.id}
                        template={template}
                        tenantId={tenantId}
                    />
                ))}
            </div>
        </div>
    );
}
