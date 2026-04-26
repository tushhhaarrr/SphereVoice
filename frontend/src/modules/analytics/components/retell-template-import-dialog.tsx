"use client";

import { useCallback, useId, useRef, useState, type ChangeEvent } from "react";
import { FileJson, Upload } from "lucide-react";

import { importRetellJson } from "@/modules/agents";
import type { TemplateScope } from "@/modules/analytics/types";
import { Badge } from "@/components/ui/badge";
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { useCreateTemplate } from "../hooks/use-templates";

const CATEGORIES = [
  "Healthcare",
  "Real Estate",
  "Customer Support",
  "Retail",
  "Education",
  "Sales",
  "Finance",
  "Other",
] as const;

export function RetellTemplateImportDialog() {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState("");
  const [name, setName] = useState("Retell Imported Flow");
  const [description, setDescription] = useState("Imported from Retell conversation-flow JSON.");
  const [category, setCategory] = useState<(typeof CATEGORIES)[number]>("Other");
  const [scope, setScope] = useState<TemplateScope>("tenant");
  const [tags, setTags] = useState("retell, imported, flow");
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const fileInputId = useId();
  const createTemplate = useCreateTemplate();

  const handleFileChange = useCallback((event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const text = typeof reader.result === "string" ? reader.result : "";
      setSource(text);

      try {
        const parsed = importRetellJson(text);
        setName(`${parsed.name} Template`);
        setError(null);
      } catch {
        setError("This file is not a valid Retell conversation-flow JSON export.");
      }
    };
    reader.onerror = () => {
      setError("Could not read the selected JSON file.");
    };
    reader.readAsText(file);
  }, []);

  const resetDialog = useCallback((nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) {
      setError(null);
    }
  }, []);

  const handleCreateTemplate = useCallback(() => {
    try {
      const parsed = importRetellJson(source);

      createTemplate.mutate(
        {
          name: name.trim() || `${parsed.name} Template`,
          description: description.trim() || undefined,
          category,
          scope,
          tags: tags
            .split(",")
            .map((tag) => tag.trim())
            .filter(Boolean),
          agent_type: "conversation_flow",
          config: {
            execution_mode: parsed.executionMode,
            global_prompt: parsed.globalPrompt,
            nodes: parsed.nodes,
            edges: parsed.edges,
            retell_metadata: parsed.retellMetadata,
          },
          language: parsed.language,
          extraction_fields: parsed.extractionFields,
        },
        {
          onSuccess: () => {
            setOpen(false);
            setError(null);
          },
        }
      );
    } catch {
      setError("This file is not a valid Retell conversation-flow JSON export.");
    }
  }, [category, createTemplate, description, name, scope, source, tags]);

  return (
    <Dialog open={open} onOpenChange={resetDialog}>
      <DialogTrigger asChild>
        <Button>
          <Upload className="mr-1.5 h-4 w-4" />
          Import Retell Template
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Import Retell Flow Template</DialogTitle>
          <DialogDescription>
            Convert Retell flow JSON into a reusable SphereVoice flow template. This only stores flow structure and context.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
            <div>
              <p className="text-sm font-medium text-slate-900">Template-only import</p>
              <p className="text-xs text-slate-600">
                The imported template keeps the flow graph, prompts, and extraction schema. SphereVoice runtime voice/provider settings remain native.
              </p>
            </div>
            <Badge variant="outline" className="border-slate-300 text-slate-700">
              Flow + Context
            </Badge>
          </div>

          <div className="flex items-center gap-3">
            <input
              id={fileInputId}
              ref={fileInputRef}
              type="file"
              accept="application/json"
              className="hidden"
              onChange={handleFileChange}
            />
            <Button variant="secondary" type="button" onClick={() => fileInputRef.current?.click()}>
              <FileJson className="mr-1 h-3.5 w-3.5" />
              Upload JSON File
            </Button>
            <Label htmlFor={fileInputId} className="text-xs text-muted-foreground">
              Retell export JSON only
            </Label>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="retell-template-name">Template Name</Label>
              <Input id="retell-template-name" value={name} onChange={(event) => setName(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="retell-template-scope">Scope</Label>
              <Select value={scope} onValueChange={(value) => setScope(value as TemplateScope)}>
                <SelectTrigger id="retell-template-scope">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="private">Private</SelectItem>
                  <SelectItem value="tenant">Tenant</SelectItem>
                  <SelectItem value="global">Global</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="retell-template-category">Category</Label>
              <Select value={category} onValueChange={(value) => setCategory(value as (typeof CATEGORIES)[number])}>
                <SelectTrigger id="retell-template-category">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((item) => (
                    <SelectItem key={item} value={item}>
                      {item}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="retell-template-tags">Tags</Label>
              <Input id="retell-template-tags" value={tags} onChange={(event) => setTags(event.target.value)} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="retell-template-description">Description</Label>
            <Textarea
              id="retell-template-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="retell-json-source">Retell JSON</Label>
            <Textarea
              id="retell-json-source"
              value={source}
              onChange={(event) => {
                setSource(event.target.value);
                if (error) {
                  setError(null);
                }
              }}
              placeholder="Paste the Retell agent export JSON here..."
              rows={16}
              className="font-mono text-xs"
            />
          </div>

          {error ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {error}
            </div>
          ) : null}

          {createTemplate.isError ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {createTemplate.error.message}
            </div>
          ) : null}

          <div className="flex items-center justify-end gap-2">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateTemplate} disabled={createTemplate.isPending || source.trim().length === 0}>
              {createTemplate.isPending ? "Creating..." : "Create Template"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}