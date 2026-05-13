"use client";

import { useCallback, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
    ArrowLeft,
    BookOpen,
    Check,
    Database,
    Loader2,
    PhoneIncoming,
    PhoneOutgoing,
    Search,
    Sparkles,
    Wand2,
    X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
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

import { useAIGenerateBase, useAIFinalize, useCreateAgent } from "../hooks/use-agents";
import type { AIGenerateBaseResult } from "../hooks/use-agents";
import type { AgentType, CallDirection } from "../types";
import { useCrmFieldVariables } from "../hooks/use-crm-field-variables";
import { useKnowledgeBases } from "@/modules/knowledge-base/hooks/use-knowledge-base";

interface CreateAgentDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    tenantId: string;
    tenantName?: string;
}

type DialogStep = "choose-type" | "ai-describe" | "ai-review" | "manual";

export function CreateAgentDialog({
    open,
    onOpenChange,
    tenantId,
    tenantName,
}: CreateAgentDialogProps) {
    const router = useRouter();
    const createAgent = useCreateAgent();
    const generateBase = useAIGenerateBase();
    const finalize = useAIFinalize();

    // ── KB context ──
    const { data: kbListData } = useKnowledgeBases({ tenantId, pageSize: 50 });
    const tenantKbs = kbListData?.items ?? [];
    const [useKbContext, setUseKbContext] = useState(false);
    const [selectedKbId, setSelectedKbId] = useState<string>("");
    const [callDirection, setCallDirection] = useState<CallDirection>("inbound");

    // ── CRM fields ──
    const [crmModule, setCrmModule] = useState("Leads");
    const { variables: crmFieldVars, isCrmConnected, isLoading: crmLoading } = useCrmFieldVariables(tenantId, crmModule);
    const [selectedCrmFields, setSelectedCrmFields] = useState<Set<string>>(new Set());
    const [recommendedFields, setRecommendedFields] = useState<Set<string>>(new Set());
    const [crmSearch, setCrmSearch] = useState("");

    const filteredCrmFields = useMemo(() => {
        if (!crmSearch) return crmFieldVars;
        const q = crmSearch.toLowerCase();
        return crmFieldVars.filter(
            (f) => f.name.toLowerCase().includes(q) || f.description.toLowerCase().includes(q),
        );
    }, [crmFieldVars, crmSearch]);

    const toggleCrmField = (fieldName: string) => {
        setSelectedCrmFields((prev) => {
            const next = new Set(prev);
            if (next.has(fieldName)) next.delete(fieldName);
            else next.add(fieldName);
            return next;
        });
    };

    // ── Dialog state ──
    const [step, setStep] = useState<DialogStep>("choose-type");
    const [type, setType] = useState<AgentType>("single_prompt");
    const [description, setDescription] = useState("");
    const [manualName, setManualName] = useState("");

    // ── Step 1 result (base generation) ──
    const [baseResult, setBaseResult] = useState<AIGenerateBaseResult | null>(null);

    // ── Editable fields in review step ──
    const [editedName, setEditedName] = useState("");
    const [editedPrompt, setEditedPrompt] = useState("");
    const [editedWelcome, setEditedWelcome] = useState("");

    const resetForm = useCallback(() => {
        setStep("choose-type");
        setType("single_prompt");
        setDescription("");
        setManualName("");
        setBaseResult(null);
        setEditedName("");
        setEditedPrompt("");
        setEditedWelcome("");
        setUseKbContext(false);
        setSelectedKbId("");
        setSelectedCrmFields(new Set());
        setRecommendedFields(new Set());
        setCrmSearch("");
        setCrmModule("Leads");
        setCallDirection("inbound");
        generateBase.reset();
        finalize.reset();
    }, [generateBase, finalize]);

    const handleOpenChange = (nextOpen: boolean) => {
        if (!nextOpen && !createAgent.isPending && !generateBase.isPending && !finalize.isPending) {
            resetForm();
        }
        onOpenChange(nextOpen);
    };

    const handleTypeSelect = (selectedType: AgentType) => {
        setType(selectedType);
        if (selectedType === "single_prompt") {
            setStep("ai-describe");
        } else {
            setStep("manual");
        }
    };

    // ── Step 1: Generate base prompt + recommended fields ──
    const handleGenerateBase = async () => {
        if (!description.trim()) return;

        let kb_context: string | undefined;
        if (useKbContext && selectedKbId) {
            const kb = tenantKbs.find((k) => k.id === selectedKbId);
            if (kb) {
                kb_context = `KB Name: ${kb.name}` + (kb.description ? `\nDescription: ${kb.description}` : "");
            }
        }

        // Collect all CRM field names to send for AI recommendation
        const allCrmFieldNames = crmFieldVars.map((f) => f.name);

        try {
            const result = await generateBase.mutateAsync({
                description: description.trim(),
                kb_context,
                language: "en",
                voice_gender: null,
                call_direction: callDirection,
                crm_fields: allCrmFieldNames.length > 0 ? allCrmFieldNames : undefined,
            });
            setBaseResult(result);
            setEditedName(result.name);
            setEditedPrompt(result.system_prompt);
            setEditedWelcome(result.welcome_message);

            // Pre-select AI-recommended fields
            const recommended = new Set(result.recommended_crm_fields);
            setRecommendedFields(recommended);
            setSelectedCrmFields(recommended);
            setCrmSearch("");

            setStep("ai-review");
        } catch {
            // Error shown via mutation state
        }
    };

    // ── Step 2: Finalize prompt with selected fields → Create agent ──
    const handleCreateAgent = async () => {
        const agentName = editedName.trim() || "AI Agent";
        const fieldsArray = Array.from(selectedCrmFields);

        try {
            let finalPrompt = editedPrompt;
            let finalWelcome = editedWelcome;
            let variables: Array<{ name: string; description: string; default_value: string; category: string }> = [];

            // If user selected CRM fields, call finalize to inject {{vars}}
            if (fieldsArray.length > 0) {
                const finalResult = await finalize.mutateAsync({
                    system_prompt: editedPrompt,
                    welcome_message: editedWelcome,
                    selected_crm_fields: fieldsArray,
                    call_direction: callDirection,
                });
                finalPrompt = finalResult.system_prompt;
                finalWelcome = finalResult.welcome_message;
                variables = finalResult.variables;
            }

            const agent = await createAgent.mutateAsync({
                tenant_id: tenantId,
                name: agentName,
                type: "single_prompt",
                call_direction: callDirection,
                config: {
                    prompt: finalPrompt,
                    welcome_message: finalWelcome,
                    ...(variables.length > 0 ? { variables } : {}),
                },
                language: "en-US",
            });

            // Auto-attach KB if opted in
            if (useKbContext && selectedKbId) {
                const { fetchWithAuth } = await import("@/lib/api-client");
                await fetchWithAuth(`/api/v1/agents/${agent.id}/knowledge-bases`, {
                    method: "POST",
                    body: JSON.stringify({ kb_id: selectedKbId }),
                });
            }

            resetForm();
            onOpenChange(false);
            router.push(`/workspace/${tenantId}/agents/${agent.id}`);
        } catch {
            // Error surfaced from mutation state
        }
    };

    const handleManualCreate = async () => {
        if (!manualName.trim()) return;
        try {
            const agent = await createAgent.mutateAsync({
                tenant_id: tenantId,
                name: manualName.trim(),
                type,
                config: {},
                language: "en-US",
            });
            resetForm();
            onOpenChange(false);
            router.push(`/workspace/${tenantId}/agents/${agent.id}`);
        } catch {
            // Error surfaced from mutation state
        }
    };

    const isBusy = createAgent.isPending || generateBase.isPending || finalize.isPending;

    return (
        <Dialog open={open} onOpenChange={handleOpenChange}>
            <DialogContent className={step === "ai-review" ? "sm:max-w-[720px]" : "sm:max-w-[500px]"}>
                {/* ────────────────────────────────────────────────────────── */}
                {/* Step: Choose Type                                         */}
                {/* ────────────────────────────────────────────────────────── */}
                {step === "choose-type" && (
                    <>
                        <DialogHeader>
                            <DialogTitle>Create Agent</DialogTitle>
                            <DialogDescription>
                                Choose how to create your agent for {tenantName ?? "this workspace"}.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="grid gap-3 py-2">
                            <button
                                type="button"
                                onClick={() => handleTypeSelect("single_prompt")}
                                className="group relative flex items-start gap-4 overflow-hidden rounded-xl border-2 border-muted bg-card p-5 text-left transition-all hover:border-primary/50 hover:bg-muted/50 hover:shadow-md"
                            >
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-500 to-purple-600 text-white">
                                    <Sparkles className="h-5 w-5" />
                                </div>
                                <div>
                                    <div className="font-semibold">Single Prompt</div>
                                    <div className="text-sm text-muted-foreground">
                                        Describe your agent and AI will generate the prompt, welcome message, and name.
                                    </div>
                                </div>
                            </button>
                            <button
                                type="button"
                                onClick={() => handleTypeSelect("conversation_flow")}
                                className="group relative flex items-start gap-4 overflow-hidden rounded-xl border-2 border-muted bg-card p-5 text-left transition-all hover:border-primary/50 hover:bg-muted/50 hover:shadow-md"
                            >
                                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-cyan-600 text-white">
                                    <Wand2 className="h-5 w-5" />
                                </div>
                                <div>
                                    <div className="font-semibold">Conversation Flow</div>
                                    <div className="text-sm text-muted-foreground">
                                        Build a visual node-based conversation flow with branching logic.
                                    </div>
                                </div>
                            </button>
                        </div>
                    </>
                )}

                {/* ────────────────────────────────────────────────────────── */}
                {/* Step 1: Describe (direction + description + KB)           */}
                {/* ────────────────────────────────────────────────────────── */}
                {step === "ai-describe" && (
                    <>
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <Sparkles className="h-5 w-5 text-violet-500" />
                                Describe Your Agent
                            </DialogTitle>
                            <DialogDescription>
                                Tell us what your agent should do. AI will generate the prompt and recommend CRM fields.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4 py-2">
                            <Textarea
                                placeholder="e.g. A friendly receptionist for a dental clinic that books appointments and answers insurance questions"
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                rows={3}
                                maxLength={2000}
                                className="resize-none"
                                autoFocus
                            />
                            <div className="flex flex-wrap gap-2">
                                {[
                                    "Healthcare appointment scheduler",
                                    "Inbound sales qualifier for SaaS",
                                    "Restaurant reservation assistant",
                                    "Real estate lead qualifier",
                                    "Customer support for e-commerce",
                                ].map((suggestion) => (
                                    <button
                                        key={suggestion}
                                        type="button"
                                        onClick={() => setDescription(suggestion)}
                                        className="rounded-full border border-border bg-muted/50 px-3 py-1 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:bg-muted"
                                    >
                                        {suggestion}
                                    </button>
                                ))}
                            </div>

                            {generateBase.isError && (
                                <p className="text-sm text-destructive">{generateBase.error.message}</p>
                            )}

                            {/* Call direction picker */}
                            <div className="flex items-center gap-3">
                                <Label className="shrink-0 text-sm">Direction</Label>
                                <div className="flex gap-2">
                                    <button
                                        type="button"
                                        onClick={() => setCallDirection("inbound")}
                                        className={`flex items-center gap-1.5 rounded-lg border-2 px-3 py-1.5 text-xs font-medium transition-all ${
                                            callDirection === "inbound"
                                                ? "border-primary bg-primary/10 text-primary"
                                                : "border-border text-muted-foreground hover:border-primary/40"
                                        }`}
                                    >
                                        <PhoneIncoming className="h-3.5 w-3.5" />
                                        Inbound
                                    </button>
                                    <button
                                        type="button"
                                        onClick={() => setCallDirection("outbound")}
                                        className={`flex items-center gap-1.5 rounded-lg border-2 px-3 py-1.5 text-xs font-medium transition-all ${
                                            callDirection === "outbound"
                                                ? "border-primary bg-primary/10 text-primary"
                                                : "border-border text-muted-foreground hover:border-primary/40"
                                        }`}
                                    >
                                        <PhoneOutgoing className="h-3.5 w-3.5" />
                                        Outbound
                                    </button>
                                </div>
                            </div>

                            {/* CRM module selector — so AI recommends fields from the right module */}
                            {isCrmConnected && (
                                <div className="flex items-center gap-3">
                                    <Label className="shrink-0 text-sm">CRM Module</Label>
                                    <Select
                                        value={crmModule}
                                        onValueChange={(val) => {
                                            setCrmModule(val);
                                            setSelectedCrmFields(new Set());
                                            setRecommendedFields(new Set());
                                            setCrmSearch("");
                                        }}
                                    >
                                        <SelectTrigger className="h-8 text-xs w-40">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="Leads">Leads</SelectItem>
                                            <SelectItem value="Contacts">Contacts</SelectItem>
                                            <SelectItem value="Deals">Deals</SelectItem>
                                            <SelectItem value="Accounts">Accounts</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <span className="text-xs text-muted-foreground">
                                        AI will recommend fields from this module
                                    </span>
                                </div>
                            )}

                            {/* KB context toggle */}
                            {tenantKbs.length > 0 && (
                                <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-3">
                                    <div className="flex items-center gap-2">
                                        <Switch
                                            id="use-kb-context"
                                            checked={useKbContext}
                                            onCheckedChange={(v) => {
                                                setUseKbContext(v);
                                                if (!v) setSelectedKbId("");
                                                else if (tenantKbs.length === 1) setSelectedKbId(tenantKbs[0].id);
                                            }}
                                        />
                                        <label
                                            htmlFor="use-kb-context"
                                            className="flex items-center gap-1.5 text-sm font-medium cursor-pointer select-none"
                                        >
                                            <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
                                            Include company knowledge base
                                        </label>
                                    </div>
                                    {useKbContext && tenantKbs.length > 1 && (
                                        <Select value={selectedKbId} onValueChange={setSelectedKbId}>
                                            <SelectTrigger className="h-8 text-xs">
                                                <SelectValue placeholder="Select a knowledge base…" />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {tenantKbs.map((kb) => (
                                                    <SelectItem key={kb.id} value={kb.id}>
                                                        <span className="flex items-center gap-2">
                                                            <BookOpen className="h-3 w-3 shrink-0" />
                                                            {kb.name}
                                                        </span>
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    )}
                                    {useKbContext && (
                                        <p className="text-xs text-muted-foreground">
                                            The AI will personalise the system prompt to reference your company KB. The KB will be auto-attached after creation.
                                        </p>
                                    )}
                                </div>
                            )}
                        </div>
                        <DialogFooter>
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={() => setStep("choose-type")}
                                disabled={isBusy}
                            >
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back
                            </Button>
                            <Button
                                type="button"
                                onClick={handleGenerateBase}
                                disabled={isBusy || description.trim().length < 5}
                                className="bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:from-violet-600 hover:to-purple-700"
                            >
                                {generateBase.isPending ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <Sparkles className="mr-2 h-4 w-4" />
                                        Generate with AI
                                    </>
                                )}
                            </Button>
                        </DialogFooter>
                    </>
                )}

                {/* ────────────────────────────────────────────────────────── */}
                {/* Step 2: Review prompt + select CRM fields + create        */}
                {/* ────────────────────────────────────────────────────────── */}
                {step === "ai-review" && baseResult && (
                    <>
                        <DialogHeader>
                            <DialogTitle className="flex items-center gap-2">
                                <Sparkles className="h-5 w-5 text-violet-500" />
                                Review &amp; Personalize
                            </DialogTitle>
                            <DialogDescription>
                                Edit the prompt, pick CRM fields for personalization, then create your agent.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="max-h-[65vh] space-y-4 overflow-y-auto py-2 pr-1">
                            {/* Agent name */}
                            <div className="space-y-1.5">
                                <Label htmlFor="ai-agent-name" className="text-xs font-medium">
                                    Agent Name
                                </Label>
                                <Input
                                    id="ai-agent-name"
                                    value={editedName}
                                    onChange={(e) => setEditedName(e.target.value)}
                                    maxLength={255}
                                    className="h-9"
                                />
                            </div>

                            {/* Welcome message */}
                            <div className="space-y-1.5">
                                <Label htmlFor="ai-welcome" className="text-xs font-medium">
                                    Welcome Message
                                </Label>
                                <Textarea
                                    id="ai-welcome"
                                    value={editedWelcome}
                                    onChange={(e) => setEditedWelcome(e.target.value)}
                                    rows={2}
                                    className="resize-none text-sm"
                                />
                            </div>

                            {/* System prompt */}
                            <div className="space-y-1.5">
                                <Label htmlFor="ai-prompt" className="text-xs font-medium">
                                    System Prompt
                                </Label>
                                <Textarea
                                    id="ai-prompt"
                                    value={editedPrompt}
                                    onChange={(e) => setEditedPrompt(e.target.value)}
                                    rows={8}
                                    className="resize-y text-xs font-mono leading-relaxed"
                                />
                                <p className="text-[11px] text-muted-foreground">
                                    This is a clean prompt without variables. Selected CRM fields below will be injected as {"{{variables}}"} when you create the agent.
                                </p>
                            </div>

                            {/* CRM field selector */}
                            {isCrmConnected && (
                                <div className="rounded-lg border border-violet-200 bg-violet-50/40 dark:border-violet-800/60 dark:bg-violet-950/20 p-3 space-y-3">
                                    <div className="flex items-center justify-between">
                                        <div className="flex items-center gap-1.5">
                                            <Database className="h-3.5 w-3.5 text-violet-600 dark:text-violet-400" />
                                            <span className="text-sm font-medium">Personalization Fields</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            {recommendedFields.size > 0 && (
                                                <span className="flex items-center gap-1 text-[10px] text-violet-500 dark:text-violet-400">
                                                    <Sparkles className="h-3 w-3" />
                                                    AI picked
                                                </span>
                                            )}
                                            {selectedCrmFields.size > 0 && (
                                                <Badge variant="secondary" className="text-[10px] bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300 border-0">
                                                    {selectedCrmFields.size} selected
                                                </Badge>
                                            )}
                                        </div>
                                    </div>
                                    <p className="text-xs text-muted-foreground">
                                        CRM fields to inject as {"{{variables}}"} in the prompt. AI-recommended fields are pre-selected — adjust as needed.
                                    </p>

                                    {/* CRM Module selector */}
                                    <div className="flex items-center gap-2">
                                        <Label className="text-xs shrink-0">Module</Label>
                                        <Select
                                            value={crmModule}
                                            onValueChange={(val) => {
                                                setCrmModule(val);
                                                setSelectedCrmFields(new Set());
                                                setRecommendedFields(new Set());
                                                setCrmSearch("");
                                            }}
                                        >
                                            <SelectTrigger className="h-7 text-xs flex-1">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="Leads">Leads</SelectItem>
                                                <SelectItem value="Contacts">Contacts</SelectItem>
                                                <SelectItem value="Deals">Deals</SelectItem>
                                                <SelectItem value="Accounts">Accounts</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>

                                    {/* Selected fields as removable chips */}
                                    {selectedCrmFields.size > 0 && (
                                        <div className="flex flex-wrap gap-1.5">
                                            {Array.from(selectedCrmFields).map((fieldName) => {
                                                const field = crmFieldVars.find((f) => f.name === fieldName);
                                                const isRecommended = recommendedFields.has(fieldName);
                                                return (
                                                    <button
                                                        key={fieldName}
                                                        type="button"
                                                        onClick={() => toggleCrmField(fieldName)}
                                                        className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium transition-colors ${
                                                            isRecommended
                                                                ? "bg-violet-100 text-violet-800 hover:bg-violet-200 dark:bg-violet-900/50 dark:text-violet-200 dark:hover:bg-violet-800"
                                                                : "bg-gray-100 text-gray-700 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                                                        }`}
                                                    >
                                                        {isRecommended && <Sparkles className="h-2.5 w-2.5 text-violet-500" />}
                                                        {field?.description?.split(" (")[0] || fieldName}
                                                        <X className="h-3 w-3 opacity-50 hover:opacity-100" />
                                                    </button>
                                                );
                                            })}
                                        </div>
                                    )}

                                    {/* Search + field list */}
                                    <div className="rounded-md border bg-background">
                                        <div className="flex items-center gap-2 border-b px-2 py-1.5">
                                            <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                            <input
                                                className="flex-1 bg-transparent text-xs outline-none placeholder:text-muted-foreground"
                                                placeholder={`Search ${crmModule} fields...`}
                                                value={crmSearch}
                                                onChange={(e) => setCrmSearch(e.target.value)}
                                            />
                                        </div>
                                        <div className="max-h-40 overflow-y-auto p-1">
                                            {crmLoading ? (
                                                <div className="flex items-center justify-center gap-2 py-4">
                                                    <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                                                    <span className="text-xs text-muted-foreground">Loading {crmModule} fields...</span>
                                                </div>
                                            ) : filteredCrmFields.length === 0 ? (
                                                <p className="px-2 py-3 text-center text-xs text-muted-foreground">
                                                    {crmSearch ? "No matching fields" : "No fields available"}
                                                </p>
                                            ) : (
                                                filteredCrmFields.map((f) => {
                                                    const isSelected = selectedCrmFields.has(f.name);
                                                    const isRecommended = recommendedFields.has(f.name);
                                                    return (
                                                        <button
                                                            key={f.name}
                                                            type="button"
                                                            onClick={() => toggleCrmField(f.name)}
                                                            className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-xs transition-colors ${
                                                                isSelected
                                                                    ? "bg-violet-50 dark:bg-violet-950/40 text-violet-800 dark:text-violet-200"
                                                                    : "hover:bg-muted/80"
                                                            }`}
                                                        >
                                                            <div
                                                                className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors ${
                                                                    isSelected
                                                                        ? "border-violet-600 bg-violet-600 text-white"
                                                                        : "border-muted-foreground/30"
                                                                }`}
                                                            >
                                                                {isSelected && <Check className="h-3 w-3" />}
                                                            </div>
                                                            <div className="flex-1 min-w-0 flex items-center gap-1.5">
                                                                <span className="font-mono font-medium">{f.name}</span>
                                                                <span className="text-muted-foreground truncate">
                                                                    {f.description.split(" (")[0]}
                                                                </span>
                                                            </div>
                                                            {isRecommended && (
                                                                <Sparkles className="h-3 w-3 shrink-0 text-violet-500" />
                                                            )}
                                                        </button>
                                                    );
                                                })
                                            )}
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Error displays */}
                            {finalize.isError && (
                                <p className="text-sm text-destructive">{finalize.error.message}</p>
                            )}
                            {createAgent.isError && (
                                <p className="text-sm text-destructive">{createAgent.error.message}</p>
                            )}
                        </div>

                        <DialogFooter>
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={() => setStep("ai-describe")}
                                disabled={isBusy}
                            >
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back
                            </Button>
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleGenerateBase}
                                disabled={isBusy || description.trim().length < 5}
                            >
                                {generateBase.isPending ? (
                                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                ) : (
                                    <Sparkles className="mr-2 h-4 w-4" />
                                )}
                                Regenerate
                            </Button>
                            <Button
                                type="button"
                                onClick={handleCreateAgent}
                                disabled={isBusy || !editedName.trim()}
                                className="bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:from-violet-600 hover:to-purple-700"
                            >
                                {(finalize.isPending || createAgent.isPending) ? (
                                    <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        {finalize.isPending ? "Personalizing..." : "Creating..."}
                                    </>
                                ) : (
                                    <>
                                        <Sparkles className="mr-2 h-4 w-4" />
                                        Create Agent
                                    </>
                                )}
                            </Button>
                        </DialogFooter>
                    </>
                )}

                {/* ────────────────────────────────────────────────────────── */}
                {/* Step: Manual (Conversation Flow)                           */}
                {/* ────────────────────────────────────────────────────────── */}
                {step === "manual" && (
                    <>
                        <DialogHeader>
                            <DialogTitle>Create Conversation Flow Agent</DialogTitle>
                            <DialogDescription>
                                Create a new flow agent for {tenantName ?? "this workspace"}.
                            </DialogDescription>
                        </DialogHeader>
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="agent-name">Name</Label>
                                <Input
                                    id="agent-name"
                                    value={manualName}
                                    onChange={(event) => setManualName(event.target.value)}
                                    placeholder="e.g. Inbound Sales Flow"
                                    maxLength={255}
                                />
                            </div>
                            <div className="rounded-md border border-dashed px-3 py-2 text-sm text-muted-foreground">
                                This agent will be created in draft status and scoped to {tenantName ?? "the current tenant workspace"}.
                            </div>
                            {createAgent.isError && (
                                <p className="text-sm text-destructive">{createAgent.error.message}</p>
                            )}
                        </div>
                        <DialogFooter>
                            <Button
                                type="button"
                                variant="ghost"
                                onClick={() => setStep("choose-type")}
                                disabled={isBusy}
                            >
                                <ArrowLeft className="mr-2 h-4 w-4" />
                                Back
                            </Button>
                            <Button
                                type="button"
                                onClick={handleManualCreate}
                                disabled={isBusy || !manualName.trim()}
                            >
                                {createAgent.isPending ? "Creating..." : "Create Agent"}
                            </Button>
                        </DialogFooter>
                    </>
                )}
            </DialogContent>
        </Dialog>
    );
}