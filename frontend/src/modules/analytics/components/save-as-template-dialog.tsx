"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
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
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { BookTemplate } from "lucide-react";
import { useCreateTemplate } from "@/modules/analytics";
import type { Agent } from "@/modules/agents/types";
import type { TemplateScope } from "../types";

interface SaveAsTemplateDialogProps {
    agent: Agent;
}

const CATEGORIES = [
    "Healthcare",
    "Real Estate",
    "Customer Support",
    "Retail",
    "Education",
    "Sales",
    "Finance",
    "Other",
];

export function SaveAsTemplateDialog({ agent }: SaveAsTemplateDialogProps) {
    const [open, setOpen] = useState(false);
    const [name, setName] = useState(agent.name + " Template");
    const [description, setDescription] = useState("");
    const [category, setCategory] = useState("Other");
    const [scope, setScope] = useState<TemplateScope>("tenant");
    const [tags, setTags] = useState("");
    const createTemplate = useCreateTemplate();

    const handleSave = () => {
        if (!name.trim() || !category) return;

        createTemplate.mutate(
            {
                name: name.trim(),
                description: description.trim() || undefined,
                category,
                scope,
                agent_type: agent.type,
                tags: tags
                    .split(",")
                    .map((t) => t.trim())
                    .filter(Boolean),
                config: agent.config,
                voice_id: agent.voice_id || undefined,
                language: agent.language,
                llm_model: agent.llm_model || undefined,
                llm_temperature: agent.llm_temperature,
                extraction_fields: agent.extraction_fields,
            },
            {
                onSuccess: () => {
                    setOpen(false);
                },
            }
        );
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                    <BookTemplate className="mr-1.5 h-4 w-4" />
                    Save as Template
                </Button>
            </DialogTrigger>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Save Agent as Template</DialogTitle>
                    <DialogDescription>
                        Create a reusable template from &quot;{agent.name}&quot;
                    </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                    <div className="space-y-2">
                        <Label htmlFor="tmpl-name">Template Name</Label>
                        <Input
                            id="tmpl-name"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                        />
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="tmpl-desc">Description</Label>
                        <Textarea
                            id="tmpl-desc"
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Brief description of what this template does..."
                            rows={3}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="tmpl-category">Category</Label>
                            <Select value={category} onValueChange={setCategory}>
                                <SelectTrigger id="tmpl-category">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    {CATEGORIES.map((cat) => (
                                        <SelectItem key={cat} value={cat}>
                                            {cat}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="tmpl-scope">Scope</Label>
                            <Select
                                value={scope}
                                onValueChange={(v) => setScope(v as TemplateScope)}
                            >
                                <SelectTrigger id="tmpl-scope">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="private">Private (only you)</SelectItem>
                                    <SelectItem value="tenant">Tenant (your org)</SelectItem>
                                    <SelectItem value="global">Global (everyone)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="tmpl-tags">Tags (comma-separated)</Label>
                        <Input
                            id="tmpl-tags"
                            value={tags}
                            onChange={(e) => setTags(e.target.value)}
                            placeholder="inbound, healthcare, appointment..."
                        />
                    </div>
                    <Button
                        onClick={handleSave}
                        disabled={createTemplate.isPending || !name.trim()}
                        className="w-full"
                    >
                        {createTemplate.isPending ? "Saving..." : "Save Template"}
                    </Button>
                    {createTemplate.isError && (
                        <p className="text-sm text-red-500">
                            {createTemplate.error.message}
                        </p>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
