"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, BookOpen, Check, Database, FlaskConical, GitBranch, Loader2, MessageSquare, Pencil, Save, Settings2, Volume2, Wrench } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { SaveAsTemplateDialog } from "@/modules/analytics";
import {
  getDefaultProviderForCategory,
  getProviderLabel,
  getProviderModels,
  getProviderSelectedModel,
  getProviderSelectedVoice,
  getProviderVoices,
  useProvidersList,
} from "@/modules/providers";
import type { Provider as RuntimeProvider } from "@/modules/providers";

import {
  createDefaultSettings,
  VoiceSettingsGroup,
  ModelSettingsGroup,
  BehaviorSettingsGroup,
  type AgentProviderBindings,
  type AgentSettings,
} from "./agent-settings";
import { FlowAgentSettingsPanel } from "./flow-agent-settings-panel";
import { FlowCanvas } from "./flow-builder";
import { FlowSettingsPanel } from "./flow-builder";
import { NodeConfigPanel } from "./flow-builder";
import { FunctionCallingConfig, type AgentFunction } from "./function-calling-config";
import { AgentCrmTab, type CrmReadMapping } from "./agent-crm-tab";
import { AgentToolsConfig } from "./agent-tools-config";
import { PromptEditor, type PromptVariable } from "./prompt-editor";
import { ScenarioList } from "./test-scenarios/scenario-list";
import { VariableSuggestTextarea } from "./variable-suggest-textarea";
import { PublishDialog } from "./publish-dialog";
import { ShareLinkDialog } from "./share-link-dialog";
import { TestCallPanel } from "./test-call-panel";
import { PhoneTestCall } from "./phone-test-call";
import { VersionHistorySidebar } from "./version-history-sidebar";
import { useAgent, usePublishAgent, useUpdateAgent } from "../hooks/use-agents";
import { useCrmFieldVariables } from "../hooks/use-crm-field-variables";
import type { Agent, AgentStatus } from "../types";
import type { FlowEdge, FlowNode, FlowValidationError, FlowValidationWarning } from "../types/flow";
import {
  normalizeFlowNodesForEditor,
  serializeFlowNodesForApi,
} from "../lib/flow-interop";

const STATUS_STYLES: Record<AgentStatus, string> = {
  draft: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200",
  published: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  archived: "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200",
};

const DEFAULT_PROMPT = `You are {{agent_name}}, a voice assistant for {{company_name}}.

Your personality:
- Warm, confident, and conversational — you sound like a real person, not a robot
- You speak in short, natural sentences (1–2 sentences per turn, under 30 words)
- You never use bullet points, numbered lists, markdown, or any visual formatting
- You mirror the caller's energy — if they're casual, be casual; if they're formal, match it

Your job:
- Greet the caller, understand what they need, and help them get it
- If you know the caller's name, use it naturally (not every sentence)
- When asked about services or products, give a brief helpful answer and ask a follow-up
- If you can't help, offer to transfer to a human at {{transfer_number}}
- Never make up information you don't have — say "I'm not sure about that, let me connect you with someone who can help"

Operational context:
- Business hours: {{business_hours}}
- Today is {{current_date}} ({{day_of_week}}), current time: {{current_time}}
- If the caller asks to schedule something outside business hours, suggest the next available window`;

const DEFAULT_VARIABLES: PromptVariable[] = [
  // System variables — auto-populated at call time, no user action needed.
  // These are injected by the backend pipeline even if not listed here,
  // but we show them so users know they exist and can use them in prompts.
  { name: "agent_name", description: "Display name of this agent (auto-filled)", defaultValue: "", category: "system" },
  { name: "company_name", description: "Client company name (auto-filled from tenant)", defaultValue: "", category: "system" },
  { name: "caller_name", description: "Caller's name if known from CRM or campaign", defaultValue: "", category: "system" },
  { name: "caller_number", description: "Caller's phone number (auto-filled)", defaultValue: "", category: "system" },
  { name: "current_date", description: "Today's date, e.g. 2026-03-25 (auto-filled)", defaultValue: "", category: "system" },
  { name: "current_time", description: "Current time, e.g. 14:30 UTC (auto-filled)", defaultValue: "", category: "system" },
  { name: "day_of_week", description: "Day name, e.g. Tuesday (auto-filled)", defaultValue: "", category: "system" },
  // CRM variables — real CRM fields are injected dynamically via useCrmFieldVariables
  // hook. No hardcoded fake placeholders.
  // Operational variables — used in the prompt, admin sets defaults
  { name: "business_hours", description: "Business operating hours shown to callers", defaultValue: "", category: "custom" },
  { name: "transfer_number", description: "Phone number for transferring to a human", defaultValue: "", category: "custom" },
  { name: "company_website", description: "Company website URL to share with callers", defaultValue: "", category: "custom" },
  { name: "support_email", description: "Support email to share with callers", defaultValue: "", category: "custom" },
];

function hydratePrompt(config: Record<string, unknown> | null | undefined): string {
  if (config && typeof config.prompt === "string" && config.prompt.length > 0) {
    return config.prompt;
  }
  return DEFAULT_PROMPT;
}

function hydrateVariables(config: Record<string, unknown> | null | undefined): PromptVariable[] {
  if (config && Array.isArray(config.variables) && config.variables.length > 0) {
    return (config.variables as Array<Record<string, string>>).map((value) => {
      // Restore category from saved data, or infer from DEFAULT_VARIABLES
      const knownVar = DEFAULT_VARIABLES.find((d) => d.name === value.name);
      return {
        name: value.name ?? "",
        description: value.description ?? "",
        defaultValue: value.default_value ?? "",
        category: (value.category as PromptVariable["category"]) ?? knownVar?.category ?? "custom",
      };
    });
  }
  return DEFAULT_VARIABLES;
}

function hydrateSettings(config: Record<string, unknown> | null | undefined): AgentSettings {
  const defaults = createDefaultSettings();
  if (config && config.settings && typeof config.settings === "object") {
    const saved = config.settings as Partial<AgentSettings>;
    // Deep-merge each section so partial saves (e.g. { voiceLanguage: { language: "hi" } })
    // don't wipe out sibling keys like voiceSpeed, ttsProvider, etc.
    const result = { ...defaults };
    for (const key of Object.keys(defaults) as Array<keyof AgentSettings>) {
      const savedVal = saved[key];
      if (savedVal !== undefined && typeof savedVal === "object" && savedVal !== null && !Array.isArray(savedVal)) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (result as any)[key] = { ...defaults[key], ...savedVal };
      } else if (savedVal !== undefined) {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (result as any)[key] = savedVal;
      }
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const pce = result.postCallExtraction as any;
    if (pce && !pce.defaults && (pce.callSummary !== undefined || pce.successBoolean !== undefined || pce.userSentiment !== undefined)) {
      pce.defaults = {
        callSummary: pce.callSummary ?? true,
        successEvaluation: pce.successBoolean ?? true,
        customerSentiment: pce.userSentiment ?? true,
        customerFrustrated: true,
        agentPerformance: true,
        actionItems: true,
        callerInfo: true,
      };
      pce.enabledCategories = pce.enabledCategories || [];
      pce.disabledFields = pce.disabledFields || [];
      delete pce.callSummary;
      delete pce.successBoolean;
      delete pce.userSentiment;
    }
    // Backfill new default groups for existing agents
    if (pce?.defaults) {
      if (pce.defaults.agentPerformance === undefined) pce.defaults.agentPerformance = true;
      if (pce.defaults.actionItems === undefined) pce.defaults.actionItems = true;
      if (pce.defaults.callerInfo === undefined) pce.defaults.callerInfo = true;
      // Migrate legacy scriptFollowed into agentPerformance
      if (pce.defaults.scriptFollowed !== undefined && pce.defaults.agentPerformance === undefined) {
        pce.defaults.agentPerformance = pce.defaults.scriptFollowed;
      }
    }

    return result;
  }
  return defaults;
}

function normalizeLanguage(language: string): string {
  return language === "en" ? "en-US" : language;
}

function resolveProviderSelection(
  selection: string | null | undefined,
  providers: RuntimeProvider[],
): RuntimeProvider | undefined {
  return (
    providers.find((provider) => provider.id === selection) ??
    providers.find((provider) => provider.provider_name === selection) ??
    providers.find((provider) => provider.provider_family === selection) ??
    providers.find((provider) => provider.is_default) ??
    providers[0]
  );
}

function getProviderFamilyLabel(provider: RuntimeProvider): string {
  return getProviderLabel(provider.provider_family || provider.provider_name);
}

function pickRepresentativeProviders(providers: RuntimeProvider[]): RuntimeProvider[] {
  const families = new Map<string, RuntimeProvider>();

  for (const provider of providers) {
    const family = provider.provider_family || provider.provider_name;
    const current = families.get(family);

    if (!current) {
      families.set(family, provider);
      continue;
    }

    if (!current.is_default && provider.is_default) {
      families.set(family, provider);
      continue;
    }

    const currentHasCatalog = getProviderModels(current).length > 0 || getProviderVoices(current).length > 0;
    const nextHasCatalog = getProviderModels(provider).length > 0 || getProviderVoices(provider).length > 0;
    if (!currentHasCatalog && nextHasCatalog) {
      families.set(family, provider);
    }
  }

  return Array.from(families.values());
}

function matchesAgentLanguage(value: string | undefined, language: string): boolean {
  if (!value) {
    return false;
  }

  const normalizedValue = value.toLowerCase();
  const normalizedLanguage = language.toLowerCase();
  return normalizedValue === normalizedLanguage || normalizedValue.startsWith(`${normalizedLanguage}-`);
}

function findProviderForModel(
  modelId: string | null | undefined,
  providers: RuntimeProvider[],
): RuntimeProvider | undefined {
  if (!modelId) {
    return providers.find((provider) => provider.is_default) ?? providers[0];
  }

  return (
    providers.find((provider) => getProviderModels(provider).some((model) => model.id === modelId)) ??
    providers.find((provider) => getProviderSelectedModel(provider) === modelId) ??
    providers.find((provider) => provider.is_default) ??
    providers[0]
  );
}

function buildLlmModelOptions(providers: RuntimeProvider[]): Array<{ value: string; label: string }> {
  const options = providers.flatMap((provider) => {
    const models = getProviderModels(provider);
    if (models.length > 0) {
      return models.map((model) => ({
        value: model.id,
        label: `${getProviderLabel(provider.provider_name)} — ${model.name}`,
      }));
    }

    const selectedModel = getProviderSelectedModel(provider);
    return selectedModel
      ? [{ value: selectedModel, label: `${getProviderLabel(provider.provider_name)} — ${selectedModel}` }]
      : [];
  });

  return Array.from(new Map(options.map((option) => [option.value, option])).values());
}

function buildSttModelOptions(provider: RuntimeProvider | undefined): Array<{ value: string; label: string }> {
  if (!provider) {
    return [];
  }

  const models = getProviderModels(provider);
  if (models.length > 0) {
    return models.map((model) => ({
      value: model.id,
      label: model.name,
    }));
  }

  const selectedModel = getProviderSelectedModel(provider);
  return selectedModel ? [{ value: selectedModel, label: selectedModel }] : [];
}

const KNOWN_TTS_FALLBACK_VOICES: Partial<Record<string, Array<{ id: string; name: string }>>> = {
  inworld: [{ id: "Ashley", name: "Ashley" }],
  sarvam: [
    { id: "aditya", name: "Aditya (Male, v3)" },
    { id: "anushka", name: "Anushka (Female, v2)" },
    { id: "shubh", name: "Shubh (Male, v3)" },
    { id: "ritu", name: "Ritu (Female, v3)" },
    { id: "priya", name: "Priya (Female, v3)" },
    { id: "rahul", name: "Rahul (Male, v3)" },
    { id: "abhilash", name: "Abhilash (Male, v2)" },
  ],
};

function buildTtsModelOptions(provider: RuntimeProvider | undefined): Array<{ value: string; label: string }> {
  if (!provider) {
    return [];
  }

  const models = getProviderModels(provider);
  if (models.length > 0) {
    return models.map((model) => ({
      value: model.id,
      label: model.name,
    }));
  }

  const selectedModel = getProviderSelectedModel(provider);
  return selectedModel ? [{ value: selectedModel, label: selectedModel }] : [];
}

function getPreferredTtsModelForLanguage(
  provider: RuntimeProvider | undefined,
  language: string,
): string | null {
  if (!provider) {
    return null;
  }

  const models = getProviderModels(provider);
  if (provider.provider_name === "inworld" || provider.provider_family === "inworld") {
    if (language.toLowerCase() !== "en") {
      return models.find((model) => model.id === "inworld-tts-1.5-max")?.id ?? null;
    }
    return models.find((model) => model.id === "inworld-tts-1.5-mini")?.id
      ?? models.find((model) => model.id === "inworld-tts-1.5-max")?.id
      ?? null;
  }

  return getProviderSelectedModel(provider);
}

function buildTtsVoiceOptions(
  provider: RuntimeProvider | undefined,
  activeVoiceId: string | null | undefined,
  selectedLanguage: string,
  selectedModel?: string,
): Array<{ value: string; label: string }> {
  if (!provider) {
    return [];
  }

  const allVoices = getProviderVoices(provider);

  // Filter voices by selected model when voices have model tags (e.g. Sarvam).
  // Voices whose tags include the selected model are kept; voices with no
  // model-like tags are always shown (other providers).
  const modelFilteredVoices = selectedModel
    ? allVoices.filter((voice) => {
      const tags = voice.tags ?? [];
      const hasModelTags = tags.some((t) => t.startsWith("bulbul:"));
      if (!hasModelTags) return true; // non-Sarvam voices or untagged
      return tags.includes(selectedModel);
    })
    : allVoices;

  // Sort language-matching voices to the top.
  const matchesLang = (voice: (typeof modelFilteredVoices)[number]) => {
    const locales = [voice.language, voice.locale, ...(voice.secondary_locales ?? [])].filter(
      (value): value is string => typeof value === "string" && value.length > 0,
    );
    if (locales.length === 0) return true;
    return locales.some((value) => matchesAgentLanguage(value, selectedLanguage));
  };

  const sorted = [...modelFilteredVoices].sort((a, b) => {
    const aMatch = matchesLang(a) ? 0 : 1;
    const bMatch = matchesLang(b) ? 0 : 1;
    return aMatch - bMatch;
  });

  const fallbackVoices = [
    ...sorted.map((voice) => ({
      value: voice.id,
      label: [
        voice.name,
        voice.locale_name || voice.locale || voice.language,
        voice.gender,
      ]
        .filter(Boolean)
        .join(" • "),
    })),
    ...(getProviderSelectedVoice(provider)
      ? [{ value: getProviderSelectedVoice(provider) as string, label: getProviderSelectedVoice(provider) as string }]
      : []),
    ...(activeVoiceId ? [{ value: activeVoiceId, label: activeVoiceId }] : []),
    ...((KNOWN_TTS_FALLBACK_VOICES[provider.provider_name] ?? []).map((voice) => ({
      value: voice.id,
      label: voice.name,
    }))),
  ];

  return Array.from(new Map(fallbackVoices.map((voice) => [voice.value, voice])).values());
}

function hydrateFunctions(config: Record<string, unknown> | null | undefined): AgentFunction[] {
  if (config && Array.isArray(config.functions) && config.functions.length > 0) {
    return config.functions as AgentFunction[];
  }
  return [];
}

function hydrateWelcomeMessage(config: Record<string, unknown> | null | undefined): string {
  if (config && typeof config.welcome_message === "string") {
    return config.welcome_message;
  }
  return "";
}

/* ------------------------------------------------------------------ */
/*  Welcome Message presets                                           */
/* ------------------------------------------------------------------ */

const WELCOME_MESSAGE_PRESETS = [
  {
    label: "Friendly Greeting",
    message: "Hi there! Thanks for calling. How can I help you today?",
  },
  {
    label: "Professional",
    message:
      "Thank you for calling {{company_name}}. My name is {{agent_name}}. How may I assist you?",
  },
  {
    label: "Healthcare",
    message:
      "Hello, this is {{agent_name}} from {{company_name}}. I'm here to help with your appointment or answer any health-related questions. How can I assist you today?",
  },
  {
    label: "Sales",
    message:
      "Hi! Thanks for reaching out to {{company_name}}. I'd love to help you find the right solution. What are you looking for today?",
  },
  {
    label: "Support",
    message:
      "Hello! You've reached {{company_name}} support. I'm here to help resolve any issues you're experiencing. What can I do for you?",
  },
  {
    label: "Scheduling",
    message:
      "Hi! I'm {{agent_name}}, your scheduling assistant at {{company_name}}. Would you like to book, reschedule, or check on an appointment?",
  },
] as const;

function WelcomeMessageEditor({
  value,
  onChange,
  variables = [],
}: {
  value: string;
  onChange: (v: string) => void;
  variables?: PromptVariable[];
}) {
  const activePreset = WELCOME_MESSAGE_PRESETS.find((p) => p.message === value);
  const isCustom = value.length > 0 && !activePreset;

  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <label htmlFor="welcome-message" className="text-sm font-medium leading-none">
          Welcome Message
        </label>
        <p className="text-xs text-muted-foreground">
          Pick a preset or write your own. The agent says this when a caller connects.
          Supports {"{{variables}}"}.
        </p>
      </div>

      {/* Preset chips */}
      <div className="flex flex-wrap gap-2">
        {WELCOME_MESSAGE_PRESETS.map((preset) => {
          const isActive = preset.message === value;
          return (
            <button
              key={preset.label}
              type="button"
              onClick={() => onChange(preset.message)}
              className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${isActive
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-muted/50 text-muted-foreground hover:border-primary/40 hover:bg-muted"
                }`}
            >
              {isActive && <Check className="h-3 w-3" />}
              {preset.label}
            </button>
          );
        })}
        <button
          type="button"
          onClick={() => {
            if (!isCustom) onChange("");
          }}
          className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-xs font-medium transition-colors ${isCustom
            ? "border-primary bg-primary text-primary-foreground"
            : "border-border bg-muted/50 text-muted-foreground hover:border-primary/40 hover:bg-muted"
            }`}
        >
          <Pencil className="h-3 w-3" />
          Custom
        </button>
      </div>

      {/* Editable textarea with variable autocomplete */}
      <VariableSuggestTextarea
        id="welcome-message"
        value={value}
        onChange={onChange}
        variables={variables}
        placeholder="Hello, this is {{agent_name}}. How can I help you today?"
      />
    </div>
  );
}

export function AgentDetailPage({ agentId, backHref }: { agentId: string; backHref: string }) {
  const router = useRouter();
  const { data: agent, isLoading, error } = useAgent(agentId);

  if (isLoading) {
    return (
      <div className="flex h-[60vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !agent) {
    return (
      <AgentDetailEditor
        key={`mock-${agentId}`}
        agentId={agentId}
        agentName="Demo Agent (Mock)"
        agentType="single_prompt"
        agentStatus="draft"
        agent={null}
        onBack={() => router.push(backHref)}
        currentVersion={0}
      />
    );
  }

  return (
    <AgentDetailEditor
      key={agent?.id ?? agentId}
      agentId={agentId}
      agentName={agent?.name ?? "Loading..."}
      agentType={agent?.type ?? "single_prompt"}
      agentStatus={agent?.status ?? "draft"}
      agent={agent ?? null}
      onBack={() => router.push(backHref)}
      currentVersion={agent?.version ?? 0}
    />
  );
}

interface AgentDetailEditorProps {
  agentId: string;
  agentName: string;
  agentType: string;
  agentStatus: AgentStatus;
  agent?: Agent | null;
  onBack: () => void;
  currentVersion: number;
}

function AgentDetailEditor({
  agentId,
  agentName,
  agentType,
  agentStatus,
  agent,
  onBack,
  currentVersion,
}: AgentDetailEditorProps) {
  const updateMutation = useUpdateAgent();
  const publishMutation = usePublishAgent();
  const config = agent?.config as Record<string, unknown> | null | undefined;
  const isFlowAgent = agentType === "conversation_flow";
  const { data: providerData } = useProvidersList({
    tenantId: agent?.tenant_id,
    enabled: !!agent?.tenant_id,
  });

  // Fetch real CRM fields so they appear in prompt editor autocomplete
  const { variables: crmFieldVars } = useCrmFieldVariables(agent?.tenant_id);

  const [prompt, setPrompt] = useState(() => hydratePrompt(config));
  const [variables, setVariables] = useState<PromptVariable[]>(() => hydrateVariables(config));
  const [agentSettings, setAgentSettings] = useState<AgentSettings>(() => {
    const base = hydrateSettings(config);
    // Prefer the dedicated DB columns over the values embedded in config.settings
    if (agent?.llm_max_tokens != null) {
      base.llm.maxTokens = agent.llm_max_tokens;
    }
    // Seed language & voiceId from DB columns when config.settings doesn't have them
    if (agent?.language && !base.voiceLanguage.language) {
      base.voiceLanguage.language = agent.language.split("-")[0]; // "en-US" → "en"
    } else if (agent?.language && base.voiceLanguage.language === "en" && agent.language.split("-")[0] !== "en") {
      // config.settings had default "en" but DB column has a real language
      base.voiceLanguage.language = agent.language.split("-")[0];
    }
    if (agent?.voice_id && !base.voiceLanguage.voiceId) {
      base.voiceLanguage.voiceId = agent.voice_id;
    }
    return base;
  });
  const [functions, setFunctions] = useState<AgentFunction[]>(() => hydrateFunctions(config));
  const [welcomeMessage, setWelcomeMessage] = useState(() => hydrateWelcomeMessage(config));

  const prevLanguageRef = useRef(agentSettings.voiceLanguage.language);
  const prevTtsModelRef = useRef(agentSettings.voiceLanguage.ttsModel);
  const [isDirty, setIsDirty] = useState(false);
  const [flowNodes, setFlowNodes] = useState<FlowNode[]>(() =>
    Array.isArray(config?.nodes) ? normalizeFlowNodesForEditor(config.nodes as FlowNode[]) : []
  );
  const [flowEdges, setFlowEdges] = useState<FlowEdge[]>(() =>
    Array.isArray(config?.edges) ? (config.edges as FlowEdge[]) : []
  );
  const [flowExecutionMode, setFlowExecutionMode] = useState<"flex" | "rigid">(
    () => (config?.execution_mode === "rigid" ? "rigid" : "flex")
  );
  const [globalPrompt, setGlobalPrompt] = useState(() =>
    typeof config?.global_prompt === "string" ? config.global_prompt : ""
  );
  const [flowRetellMetadata] = useState<Record<string, unknown> | null>(() =>
    config?.retell_metadata && typeof config.retell_metadata === "object"
      ? (config.retell_metadata as Record<string, unknown>)
      : null
  );
  const [crmReadMapping, setCrmReadMapping] = useState<CrmReadMapping>(() => {
    const saved = config?.crmReadMapping as CrmReadMapping | undefined;
    return saved ?? { crmModule: "Leads", mapping: {} };
  });
  const [showVersionSidebar, setShowVersionSidebar] = useState(false);
  const [selectedFlowNodeId, setSelectedFlowNodeId] = useState<string | null>(null);

  const availableProviders = useMemo(() => providerData?.providers ?? [], [providerData?.providers]);
  const ttsProviders = useMemo(
    () => availableProviders.filter((provider) => provider.provider_category === "tts" && provider.is_active),
    [availableProviders],
  );
  const llmProviders = useMemo(
    () => availableProviders.filter((provider) => provider.provider_category === "llm" && provider.is_active),
    [availableProviders],
  );
  const sttProviders = useMemo(
    () => availableProviders.filter((provider) => provider.provider_category === "stt" && provider.is_active),
    [availableProviders],
  );
  const ttsFamilyProviders = useMemo(() => pickRepresentativeProviders(ttsProviders), [ttsProviders]);
  const llmFamilyProviders = useMemo(() => pickRepresentativeProviders(llmProviders), [llmProviders]);
  const sttFamilyProviders = useMemo(() => pickRepresentativeProviders(sttProviders), [sttProviders]);

  const effectiveAgentSettings = (() => {
    const defaultTtsProvider =
      resolveProviderSelection(agentSettings.voiceLanguage.ttsProvider, ttsFamilyProviders) ??
      (agent?.tts_provider_id
        ? ttsFamilyProviders.find((provider) => provider.id === agent.tts_provider_id)
        : undefined) ??
      getDefaultProviderForCategory(ttsFamilyProviders, "tts");
    const defaultLlmProvider =
      resolveProviderSelection(agentSettings.llm.provider, llmFamilyProviders) ??
      findProviderForModel(agentSettings.llm.model || agent?.llm_model, llmFamilyProviders) ??
      (agent?.llm_provider_id
        ? llmFamilyProviders.find((provider) => provider.id === agent.llm_provider_id)
        : undefined) ??
      getDefaultProviderForCategory(llmFamilyProviders, "llm");
    const defaultSttProvider =
      resolveProviderSelection(agentSettings.transcription.sttProvider, sttFamilyProviders) ??
      (agent?.stt_provider_id
        ? sttFamilyProviders.find((provider) => provider.id === agent.stt_provider_id)
        : undefined) ??
      getDefaultProviderForCategory(sttFamilyProviders, "stt");

    return {
      ...agentSettings,
      voiceLanguage: {
        ...agentSettings.voiceLanguage,
        ttsProvider: defaultTtsProvider?.id ?? agentSettings.voiceLanguage.ttsProvider,
        ttsModel:
          agentSettings.voiceLanguage.ttsModel ||
          (defaultTtsProvider
            ? getPreferredTtsModelForLanguage(defaultTtsProvider, agentSettings.voiceLanguage.language)
            : null) ||
          "",
        voiceId:
          agentSettings.voiceLanguage.voiceId ||
          agent?.voice_id ||
          (defaultTtsProvider ? getProviderSelectedVoice(defaultTtsProvider) : null) ||
          "",
      },
      llm: {
        ...agentSettings.llm,
        provider: defaultLlmProvider?.id ?? agentSettings.llm.provider,
        model:
          agentSettings.llm.model ||
          agent?.llm_model ||
          (defaultLlmProvider ? getProviderSelectedModel(defaultLlmProvider) : null) ||
          "",
      },
      transcription: {
        ...agentSettings.transcription,
        sttProvider: defaultSttProvider?.id ?? agentSettings.transcription.sttProvider,
        sttModel:
          agentSettings.transcription.sttModel ||
          (defaultSttProvider ? getProviderSelectedModel(defaultSttProvider) : null) ||
          "",
      },
    } satisfies AgentSettings;
  })();

  const providerBindings = useMemo<AgentProviderBindings>(() => {
    const selectedTtsProvider = resolveProviderSelection(effectiveAgentSettings.voiceLanguage.ttsProvider, ttsFamilyProviders);
    const selectedSttProvider = resolveProviderSelection(effectiveAgentSettings.transcription.sttProvider, sttFamilyProviders);
    const selectedLlmProvider = resolveProviderSelection(effectiveAgentSettings.llm.provider, llmFamilyProviders);

    return {
      sttProviders: sttFamilyProviders.map((provider) => ({
        value: provider.id,
        label: getProviderFamilyLabel(provider),
      })),
      sttModels: buildSttModelOptions(selectedSttProvider),
      llmProviders: llmFamilyProviders.map((provider) => ({
        value: provider.id,
        label: getProviderFamilyLabel(provider),
      })),
      ttsProviders: ttsFamilyProviders.map((provider) => ({
        value: provider.id,
        label: getProviderFamilyLabel(provider),
      })),
      ttsModels: buildTtsModelOptions(selectedTtsProvider),
      ttsVoices: buildTtsVoiceOptions(
        selectedTtsProvider,
        effectiveAgentSettings.voiceLanguage.voiceId,
        effectiveAgentSettings.voiceLanguage.language,
        effectiveAgentSettings.voiceLanguage.ttsModel,
      ),
      llmModels: buildLlmModelOptions(selectedLlmProvider ? [selectedLlmProvider] : llmFamilyProviders),
    };
  }, [
    effectiveAgentSettings.transcription.sttProvider,
    effectiveAgentSettings.voiceLanguage.language,
    effectiveAgentSettings.voiceLanguage.ttsModel,
    effectiveAgentSettings.voiceLanguage.ttsProvider,
    effectiveAgentSettings.voiceLanguage.voiceId,
    effectiveAgentSettings.llm.provider,
    llmFamilyProviders,
    sttFamilyProviders,
    ttsFamilyProviders,
  ]);

  const handlePromptChange = useCallback((value: string) => {
    setPrompt(value);
    setIsDirty(true);
  }, []);

  const handleSettingsChange = useCallback(
    (nextSettings: AgentSettings) => {
      const prevLang = prevLanguageRef.current;
      const newLang = nextSettings.voiceLanguage.language;
      const prevModel = prevTtsModelRef.current;
      const newModel = nextSettings.voiceLanguage.ttsModel;
      setAgentSettings(nextSettings);
      setIsDirty(true);

      const languageChanged = newLang !== prevLang;
      const modelChanged = newModel !== prevModel;

      // Auto-select a compatible voice when language or TTS model changes
      if (languageChanged || modelChanged) {
        if (languageChanged) prevLanguageRef.current = newLang;
        if (modelChanged) prevTtsModelRef.current = newModel;

        const currentTtsProvider = resolveProviderSelection(
          nextSettings.voiceLanguage.ttsProvider,
          ttsFamilyProviders,
        );
        const currentVoiceId = nextSettings.voiceLanguage.voiceId;
        const selectedVoice = currentTtsProvider && currentVoiceId
          ? getProviderVoices(currentTtsProvider).find((v) => v.id === currentVoiceId)
          : undefined;
        const voiceGender = selectedVoice?.gender ?? null;

        if (currentTtsProvider) {
          let candidateVoices = getProviderVoices(currentTtsProvider);

          // Filter by model tag when a model is selected (e.g. bulbul:v2 vs v3)
          if (newModel) {
            const modelFiltered = candidateVoices.filter((voice) => {
              const tags = voice.tags ?? [];
              const hasModelTags = tags.some((t) => t.startsWith("bulbul:"));
              if (!hasModelTags) return true;
              return tags.includes(newModel);
            });
            if (modelFiltered.length > 0) candidateVoices = modelFiltered;
          }

          // Then filter by language
          const voicesForLang = candidateVoices.filter((voice) => {
            const locales = [voice.language, voice.locale, ...(voice.secondary_locales ?? [])].filter(
              (v): v is string => typeof v === "string" && v.length > 0,
            );
            return locales.some((v) => matchesAgentLanguage(v, newLang));
          });

          // Pick from language matches first, then all model-compatible voices
          const pool = voicesForLang.length > 0 ? voicesForLang : candidateVoices;

          // Check if current voice is still compatible
          const currentStillValid = pool.some((v) => v.id === currentVoiceId);
          if (!currentStillValid && pool.length > 0) {
            const sameGenderMatch = voiceGender
              ? pool.find((v) => v.gender === voiceGender)
              : undefined;
            const bestMatch = sameGenderMatch ?? pool[0];
            setAgentSettings((prev) => ({
              ...prev,
              voiceLanguage: { ...prev.voiceLanguage, voiceId: bestMatch.id },
            }));
          }
        }
      }
    },
    [ttsFamilyProviders],
  );

  const handleAddVariable = useCallback((variable: PromptVariable) => {
    setVariables((previous) => {
      if (previous.some((entry) => entry.name === variable.name)) {
        return previous;
      }
      setIsDirty(true);
      return [...previous, variable];
    });
  }, []);

  const handleVariableChange = useCallback((name: string, defaultValue: string) => {
    setVariables((previous) => {
      const exists = previous.some((v) => v.name === name);
      if (exists) {
        return previous.map((v) => (v.name === name ? { ...v, defaultValue } : v));
      }
      // Variable used in prompt but not in the list yet — add it
      return [...previous, { name, description: "", defaultValue, category: "custom" as const }];
    });
    setIsDirty(true);
  }, []);

  const handleVariableRemove = useCallback((name: string) => {
    setVariables((previous) => previous.filter((v) => v.name !== name));
    setIsDirty(true);
  }, []);

  const handleFunctionsChange = useCallback((nextFunctions: AgentFunction[]) => {
    setFunctions(nextFunctions);
    setIsDirty(true);
  }, []);

  const handleWelcomeMessageChange = useCallback((value: string) => {
    setWelcomeMessage(value);
    setIsDirty(true);
  }, []);

  const buildDraftUpdateData = useCallback((): Partial<Agent> | null => {
    if (!agent) {
      return null;
    }

    const selectedTtsProvider =
      resolveProviderSelection(effectiveAgentSettings.voiceLanguage.ttsProvider, ttsFamilyProviders) ??
      getDefaultProviderForCategory(ttsFamilyProviders, "tts");
    const selectedLlmProvider =
      resolveProviderSelection(effectiveAgentSettings.llm.provider, llmFamilyProviders) ??
      findProviderForModel(effectiveAgentSettings.llm.model, llmFamilyProviders) ??
      getDefaultProviderForCategory(llmFamilyProviders, "llm");
    const defaultSttProvider =
      resolveProviderSelection(effectiveAgentSettings.transcription.sttProvider, availableProviders) ??
      (agent.stt_provider_id
        ? availableProviders.find((provider) => provider.id === agent.stt_provider_id)
        : undefined) ?? getDefaultProviderForCategory(availableProviders, "stt");
    const defaultTelephonyProvider =
      (agent.telephony_provider_id
        ? availableProviders.find((provider) => provider.id === agent.telephony_provider_id)
        : undefined) ?? getDefaultProviderForCategory(availableProviders, "telephony");

    // Preserve the server's original config.settings as a base layer.
    // Only overlay user-changed sections. This prevents frontend defaults
    // (like optimizeFor: "speed", sttModel: "") from being injected into
    // agents that had no settings — which caused cross-provider model bugs.
    // The settings form always shows the hydrated state, so agentSettings
    // is the correct value to save — the backend factory's
    // _get_agent_stt_model_override() already guards against cross-provider
    // model name leaks (optimizeFor only maps for Deepgram).
    const settingsToSave = agentSettings;

    // Only send variables if the agent previously had custom variables or
    // the user explicitly modified them. Prevents injecting DEFAULT_VARIABLES
    // (with placeholder values like "Acme Corp") into agents that had none.
    const serverVariables = (agent.config as Record<string, unknown>)?.variables;
    const hadServerVariables = Array.isArray(serverVariables) && serverVariables.length > 0;
    const currentVarsSerialized = variables.map((variable) => ({
      name: variable.name,
      description: variable.description,
      default_value: variable.defaultValue,
      category: variable.category ?? "custom",
    }));
    const defaultVarsSerialized = DEFAULT_VARIABLES.map((v) => ({
      name: v.name,
      description: v.description,
      default_value: v.defaultValue,
      category: v.category ?? "custom",
    }));
    const varsAreDefaults = JSON.stringify(currentVarsSerialized) === JSON.stringify(defaultVarsSerialized);
    const variablesToSave = hadServerVariables || !varsAreDefaults
      ? currentVarsSerialized
      : (serverVariables as Array<Record<string, string>>) ?? [];

    const baseConfig = {
      ...(agent.config || {}),
      prompt,
      welcome_message: welcomeMessage,
      variables: variablesToSave,
      settings: settingsToSave,
      functions,
      crmReadMapping,
    };

    const nextConfig = isFlowAgent
      ? {
        ...baseConfig,
        nodes: serializeFlowNodesForApi(flowNodes),
        edges: flowEdges,
        execution_mode: flowExecutionMode,
        global_prompt: globalPrompt,
        ...(flowRetellMetadata ? { retell_metadata: flowRetellMetadata } : {}),
      }
      : baseConfig;

    // Provider IDs: agents are created with explicit default provider IDs
    // resolved from the backend's provider catalog. On save, always send the
    // currently selected (or effective) provider so the value stays concrete.
    const sttProviderId = defaultSttProvider?.id ?? agent.stt_provider_id ?? null;
    const llmProviderId = selectedLlmProvider?.id ?? agent.llm_provider_id ?? null;
    const ttsProviderId = selectedTtsProvider?.id ?? agent.tts_provider_id ?? null;
    const telephonyProviderId = defaultTelephonyProvider?.id ?? agent.telephony_provider_id ?? null;

    return {
      config: nextConfig,
      language: normalizeLanguage(effectiveAgentSettings.voiceLanguage.language),
      voice_id:
        effectiveAgentSettings.voiceLanguage.voiceId ||
        (selectedTtsProvider ? getProviderSelectedVoice(selectedTtsProvider) : null) ||
        agent.voice_id ||
        null,
      voice_speed: effectiveAgentSettings.voiceLanguage.voiceSpeed,
      voice_volume: effectiveAgentSettings.voiceLanguage.voiceVolume,
      llm_model:
        effectiveAgentSettings.llm.model ||
        (selectedLlmProvider ? getProviderSelectedModel(selectedLlmProvider) : null) ||
        agent.llm_model ||
        null,
      llm_temperature: effectiveAgentSettings.llm.temperature,
      llm_max_tokens: effectiveAgentSettings.llm.maxTokens,
      stt_provider_id: sttProviderId,
      llm_provider_id: llmProviderId,
      tts_provider_id: ttsProviderId,
      telephony_provider_id: telephonyProviderId,
      max_call_duration_seconds: effectiveAgentSettings.callBehavior.maxCallDurationMinutes * 60,
      end_on_silence_seconds: effectiveAgentSettings.callBehavior.endOnSilenceSeconds,
      ring_duration_seconds: effectiveAgentSettings.callBehavior.ringDurationSeconds,
      voicemail_detection: effectiveAgentSettings.callBehavior.voicemailDetection,
      extraction_fields: effectiveAgentSettings.postCallExtraction.customFields.map((field) => ({ ...field })),
      webhook_url: effectiveAgentSettings.webhooks.url || null,
      webhook_events: effectiveAgentSettings.webhooks.events,
    };
  }, [
    agent,
    agentSettings,
    availableProviders,
    crmReadMapping,
    effectiveAgentSettings,
    flowEdges,
    flowExecutionMode,
    flowNodes,
    flowRetellMetadata,
    functions,
    globalPrompt,
    isFlowAgent,
    llmFamilyProviders,
    prompt,
    ttsFamilyProviders,
    variables,
    welcomeMessage,
  ]);

  const handleSave = useCallback(async () => {
    const data = buildDraftUpdateData();
    if (!data) return;

    await updateMutation.mutateAsync({
      id: agentId,
      data,
    });
    setIsDirty(false);
  }, [agentId, buildDraftUpdateData, updateMutation]);

  const handlePublish = useCallback(async () => {
    if (isDirty) {
      await handleSave();
    }
    await publishMutation.mutateAsync(agentId);
  }, [agentId, handleSave, isDirty, publishMutation]);

  const handleFlowNodesChange = useCallback((nextNodes: FlowNode[]) => {
    setFlowNodes(nextNodes);
    setIsDirty(true);
  }, []);

  const handleFlowEdgesChange = useCallback((nextEdges: FlowEdge[]) => {
    setFlowEdges(nextEdges);
    setIsDirty(true);
  }, []);

  const handleFlowExecutionModeChange = useCallback((mode: "flex" | "rigid") => {
    setFlowExecutionMode(mode);
    setIsDirty(true);
  }, []);

  const handleFlowNodeUpdate = useCallback((nodeId: string, partial: Partial<FlowNode["data"]>) => {
    setFlowNodes((currentNodes) => {
      const nextNodes = currentNodes.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, ...partial } as FlowNode["data"] }
          : node
      ) as FlowNode[];
      return nextNodes;
    });
    setIsDirty(true);
  }, []);

  const selectedFlowNode = useMemo(
    () => flowNodes.find((node) => node.id === selectedFlowNodeId) ?? null,
    [flowNodes, selectedFlowNodeId]
  );

  // Merge CRM variables into the variables list:
  // Only add CRM read-mapped variables from the agent's CRM tab config.
  // Real CRM fields are passed separately via crmFieldsForPicker for the picker UI.
  const variablesWithCrm = useMemo(() => {
    const existingNames = new Set(variables.map((v) => v.name));
    const extras: PromptVariable[] = [];

    // Add CRM read-mapped variables (from the agent's CRM tab)
    for (const [varName, crmFieldName] of Object.entries(crmReadMapping.mapping)) {
      if (!existingNames.has(varName)) {
        extras.push({
          name: varName,
          description: `Populated from CRM field "${crmFieldName}" (${crmReadMapping.crmModule})`,
          defaultValue: "",
          category: "crm",
        });
        existingNames.add(varName);
      }
    }

    if (extras.length === 0) return variables;

    // Tag existing variables that are CRM-mapped but lack the category
    const tagged = variables.map((v) => {
      if (v.category !== "crm" && crmReadMapping.mapping[v.name]) {
        return { ...v, category: "crm" as const };
      }
      return v;
    });
    return [...tagged, ...extras];
  }, [variables, crmReadMapping]);

  return (
    <AgentDetailContent
      agentId={agentId}
      agentName={agentName}
      agentType={agentType}
      agentStatus={agentStatus}
      agent={agent}
      prompt={prompt}
      variables={variablesWithCrm}
      crmFieldsForPicker={crmFieldVars}
      agentSettings={effectiveAgentSettings}
      functions={functions}
      flowNodes={flowNodes}
      flowEdges={flowEdges}
      flowExecutionMode={flowExecutionMode}
      globalPrompt={globalPrompt}
      selectedFlowNode={selectedFlowNode}
      isDirty={isDirty}
      isSaving={updateMutation.isPending}
      isPublishing={publishMutation.isPending}
      showVersionSidebar={showVersionSidebar}
      onPromptChange={handlePromptChange}
      onSettingsChange={handleSettingsChange}
      onAddVariable={handleAddVariable}
      onVariableChange={handleVariableChange}
      onVariableRemove={handleVariableRemove}
      onFunctionsChange={handleFunctionsChange}
      welcomeMessage={welcomeMessage}
      onWelcomeMessageChange={handleWelcomeMessageChange}
      onFlowNodesChange={handleFlowNodesChange}
      onFlowEdgesChange={handleFlowEdgesChange}
      onFlowNodeUpdate={handleFlowNodeUpdate}
      onFlowExecutionModeChange={handleFlowExecutionModeChange}
      onGlobalPromptChange={setGlobalPrompt}
      onSelectedFlowNodeChange={setSelectedFlowNodeId}
      onClearSelectedFlowNode={() => setSelectedFlowNodeId(null)}
      onSave={handleSave}
      onPublish={handlePublish}
      onToggleVersionSidebar={() => setShowVersionSidebar((value) => !value)}
      onBack={onBack}
      currentVersion={currentVersion}
      providerBindings={providerBindings}
      crmReadMapping={crmReadMapping}
      onCrmReadMappingChange={(m) => { setCrmReadMapping(m); setIsDirty(true); }}
    />
  );
}

interface AgentDetailContentProps {
  agentId: string;
  agentName: string;
  agentType: string;
  agentStatus: AgentStatus;
  agent?: Agent | null;
  prompt: string;
  variables: PromptVariable[];
  crmFieldsForPicker: PromptVariable[];
  agentSettings: AgentSettings;
  functions: AgentFunction[];
  flowNodes: FlowNode[];
  flowEdges: FlowEdge[];
  flowExecutionMode: "flex" | "rigid";
  globalPrompt: string;
  selectedFlowNode: FlowNode | null;
  isDirty: boolean;
  isSaving: boolean;
  isPublishing: boolean;
  showVersionSidebar: boolean;
  onPromptChange: (value: string) => void;
  onSettingsChange: (settings: AgentSettings) => void;
  onAddVariable: (variable: PromptVariable) => void;
  onVariableChange: (name: string, defaultValue: string) => void;
  onVariableRemove: (name: string) => void;
  onFunctionsChange: (functions: AgentFunction[]) => void;
  welcomeMessage: string;
  onWelcomeMessageChange: (value: string) => void;
  onFlowNodesChange: (nodes: FlowNode[]) => void;
  onFlowEdgesChange: (edges: FlowEdge[]) => void;
  onFlowNodeUpdate: (nodeId: string, data: Partial<FlowNode["data"]>) => void;
  onFlowExecutionModeChange: (mode: "flex" | "rigid") => void;
  onGlobalPromptChange: (prompt: string) => void;
  onSelectedFlowNodeChange: (nodeId: string | null) => void;
  onClearSelectedFlowNode: () => void;
  onSave: () => void;
  onPublish: () => void;
  onToggleVersionSidebar: () => void;
  onBack: () => void;
  currentVersion: number;
  providerBindings: AgentProviderBindings;
  crmReadMapping: CrmReadMapping;
  onCrmReadMappingChange: (mapping: CrmReadMapping) => void;
}

function AgentDetailContent({
  agentId,
  agentName,
  agentType,
  agentStatus,
  agent,
  prompt,
  variables,
  crmFieldsForPicker,
  agentSettings,
  functions,
  flowNodes,
  flowEdges,
  flowExecutionMode,
  globalPrompt,
  selectedFlowNode,
  isDirty,
  isSaving,
  isPublishing,
  showVersionSidebar,
  onPromptChange,
  onSettingsChange,
  onAddVariable,
  onVariableChange,
  onVariableRemove,
  onFunctionsChange,
  welcomeMessage,
  onWelcomeMessageChange,
  onFlowNodesChange,
  onFlowEdgesChange,
  onFlowNodeUpdate,
  onFlowExecutionModeChange,
  onGlobalPromptChange,
  onSelectedFlowNodeChange,
  onClearSelectedFlowNode,
  onSave,
  onPublish,
  onToggleVersionSidebar,
  onBack,
  currentVersion,
  providerBindings,
  crmReadMapping,
  onCrmReadMappingChange,
}: AgentDetailContentProps) {
  const isFlowAgent = agentType === "conversation_flow";
  const [activeEditorTab, setActiveEditorTab] = useState("prompt");

  return (
    <div className="flex h-full min-h-0 flex-col gap-6 px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={onBack}>
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back
          </Button>
          <Separator orientation="vertical" className="h-6" />
          <div>
            <h1 className="text-xl font-semibold">{agentName}</h1>
            <div className="flex items-center gap-2">
              <Badge className={STATUS_STYLES[agentStatus]}>{agentStatus}</Badge>
              <Badge variant="outline" className="text-xs">
                {isFlowAgent ? "Conversation Flow" : "Single Prompt"}
              </Badge>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isDirty && (
            <Badge variant="outline" className="border-orange-300 text-orange-500">
              Unsaved changes
            </Badge>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={onToggleVersionSidebar}
            title="Version history"
          >
            <GitBranch className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onSave}
            disabled={!isDirty || isSaving}
          >
            {isSaving ? (
              <Loader2 className="mr-1 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="mr-1 h-3.5 w-3.5" />
            )}
            Save
          </Button>
          {agent && <SaveAsTemplateDialog agent={agent} />}
          {agent && <ShareLinkDialog agentId={agentId} agentName={agentName} />}
          <PublishDialog
            agentName={agentName}
            currentVersion={currentVersion}
            validation={null}
            isPublishing={isPublishing}
            onPublish={onPublish}
            onValidate={() => {
              const errors: FlowValidationError[] = [];
              const warnings: FlowValidationWarning[] = [];
              if (!prompt || prompt.trim().length === 0) {
                errors.push({ nodeId: null, message: "System prompt is empty", type: "missing_required_field" });
              }
              if (!agentSettings.llm.provider && !agentSettings.llm.model) {
                errors.push({ nodeId: null, message: "LLM provider and model are not configured", type: "missing_required_field" });
              }
              if (!agentSettings.voiceLanguage.ttsProvider) {
                warnings.push({ nodeId: null, message: "TTS provider is not configured — voice output may not work", type: "empty_prompt" });
              }
              return { valid: errors.length === 0, errors, warnings };
            }}
          />
        </div>
      </div>

      <Separator />

      {isFlowAgent ? (
        <div className="grid min-h-0 flex-1 gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
          <div className="min-h-[640px] xl:h-full">
            <FlowCanvas
              initialNodes={flowNodes}
              initialEdges={flowEdges}
              onNodesChange={onFlowNodesChange}
              onEdgesChange={onFlowEdgesChange}
              onSelectedNodeChange={onSelectedFlowNodeChange}
            />
          </div>
          <FlowAgentSidebar
            agentId={agentId}
            settings={agentSettings}
            executionMode={flowExecutionMode}
            globalPrompt={globalPrompt}
            selectedNode={selectedFlowNode}
            providerBindings={providerBindings}
            onSettingsChange={onSettingsChange}
            onExecutionModeChange={onFlowExecutionModeChange}
            onGlobalPromptChange={onGlobalPromptChange}
            onNodeUpdate={onFlowNodeUpdate}
            onClearSelectedNode={onClearSelectedFlowNode}
          />
        </div>
      ) : (
        <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-[1fr_400px]">
          {/* Left: Tabbed settings */}
          <Tabs value={activeEditorTab} onValueChange={setActiveEditorTab} className="flex min-h-0 flex-col">
            <TabsList className="w-fit">
              <TabsTrigger value="prompt">
                <MessageSquare className="mr-1.5 h-3.5 w-3.5" />
                Prompt
              </TabsTrigger>
              <TabsTrigger value="voice">
                <Volume2 className="mr-1.5 h-3.5 w-3.5" />
                Voice
              </TabsTrigger>
              <TabsTrigger value="model">
                <BookOpen className="mr-1.5 h-3.5 w-3.5" />
                Model
              </TabsTrigger>
              <TabsTrigger value="behavior">
                <Settings2 className="mr-1.5 h-3.5 w-3.5" />
                Behavior
              </TabsTrigger>
              <TabsTrigger value="tools">
                <Wrench className="mr-1.5 h-3.5 w-3.5" />
                Tools
              </TabsTrigger>
              <TabsTrigger value="crm">
                <Database className="mr-1.5 h-3.5 w-3.5" />
                CRM
              </TabsTrigger>
              <TabsTrigger value="scenarios">
                <FlaskConical className="mr-1.5 h-3.5 w-3.5" />
                Test Scenarios
              </TabsTrigger>
            </TabsList>

            <TabsContent value="prompt" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="flex flex-col gap-4 pr-4">
                  <WelcomeMessageEditor
                    value={welcomeMessage}
                    onChange={onWelcomeMessageChange}
                    variables={variables}
                  />
                  <PromptEditor
                    value={prompt}
                    onChange={onPromptChange}
                    variables={variables}
                    crmFieldsForPicker={crmFieldsForPicker}
                    onAddVariable={onAddVariable}
                    onVariableChange={onVariableChange}
                    onVariableRemove={onVariableRemove}
                    height="500px"
                  />
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="voice" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="pr-4">
                  <VoiceSettingsGroup
                    settings={agentSettings}
                    onChange={onSettingsChange}
                    providerBindings={providerBindings}
                  />
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="model" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="pr-4">
                  <ModelSettingsGroup
                    settings={agentSettings}
                    onChange={onSettingsChange}
                    providerBindings={providerBindings}
                    agentId={agentId}
                    tenantId={agent?.tenant_id}
                  />
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="behavior" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="pr-4">
                  <BehaviorSettingsGroup
                    settings={agentSettings}
                    onChange={onSettingsChange}
                    agentId={agentId}
                    tenantId={agent?.tenant_id}
                    agentPrompt={prompt}
                    functionsSlot={
                      <FunctionCallingConfig
                        functions={functions}
                        onChange={onFunctionsChange}
                      />
                    }
                  />
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="tools" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="pr-4">
                  <AgentToolsConfig
                    agentId={agentId}
                    tenantId={agent?.tenant_id}
                  />
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="crm" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="pr-4">
                  <AgentCrmTab
                    agentId={agentId}
                    tenantId={agent?.tenant_id}
                    variables={variables}
                    readMapping={crmReadMapping}
                    onReadMappingChange={onCrmReadMappingChange}
                    writebackSettings={agentSettings.crmWriteback}
                    onWritebackChange={(patch) => {
                      onSettingsChange({
                        ...agentSettings,
                        crmWriteback: { ...agentSettings.crmWriteback, ...patch },
                      });
                    }}
                    postCallExtraction={agentSettings.postCallExtraction}
                    onNavigateToExtraction={() => setActiveEditorTab("behavior")}
                    onAddExtractionFields={(newFields) => {
                      const existing = agentSettings.postCallExtraction?.customFields ?? [];
                      const existingNames = new Set(existing.map((f) => f.name));
                      const deduped = newFields.filter((f) => !existingNames.has(f.name));
                      if (deduped.length === 0) return;
                      onSettingsChange({
                        ...agentSettings,
                        postCallExtraction: {
                          ...agentSettings.postCallExtraction,
                          enabled: true,
                          customFields: [...existing, ...deduped],
                        },
                      });
                    }}
                  />
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="scenarios" className="mt-4 min-h-0 flex-1">
              <ScrollArea className="h-full">
                <div className="pr-4">
                  <ScenarioList agentId={agentId} />
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>

          {/* Right: Test Call (always visible) */}
          <div className="flex min-h-0 flex-1 flex-col">
            <TestCallPanel agentId={agentId} agentSettings={agentSettings} prompt={prompt} variables={variables} crmReadMapping={crmReadMapping} />

          </div>
        </div>
      )}

      {showVersionSidebar && (
        <VersionHistorySidebar
          agentId={agentId}
          currentVersion={currentVersion}
          onClose={onToggleVersionSidebar}
        />
      )}
    </div>
  );
}

interface FlowAgentSidebarProps {
  agentId: string;
  settings: AgentSettings;
  executionMode: "flex" | "rigid";
  globalPrompt: string;
  selectedNode: FlowNode | null;
  providerBindings: AgentProviderBindings;
  onSettingsChange: (settings: AgentSettings) => void;
  onExecutionModeChange: (mode: "flex" | "rigid") => void;
  onGlobalPromptChange: (prompt: string) => void;
  onNodeUpdate: (nodeId: string, data: Partial<FlowNode["data"]>) => void;
  onClearSelectedNode: () => void;
}

function FlowAgentSidebar({
  agentId,
  settings,
  executionMode,
  globalPrompt,
  selectedNode,
  providerBindings,
  onSettingsChange,
  onExecutionModeChange,
  onGlobalPromptChange,
  onNodeUpdate,
  onClearSelectedNode,
}: FlowAgentSidebarProps) {
  const [activeTab, setActiveTab] = useState("settings");
  const currentTab = selectedNode ? "node" : activeTab;

  return (
    <div className="min-h-[640px] overflow-hidden rounded-xl border bg-background xl:h-full">
      <Tabs value={currentTab} onValueChange={setActiveTab} className="flex h-full flex-col">
        <div className="border-b p-3">
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="settings">Global Settings</TabsTrigger>
            <TabsTrigger value="node">Node</TabsTrigger>
            <TabsTrigger value="test">Test Agent</TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="settings" className="mt-0 flex-1 overflow-hidden">
          <ScrollArea className="h-full px-3 pb-3">
            <div className="space-y-4 py-3">
              <FlowSettingsPanel
                executionMode={executionMode}
                globalPrompt={globalPrompt}
                onExecutionModeChange={onExecutionModeChange}
                onGlobalPromptChange={onGlobalPromptChange}
              />
              <FlowAgentSettingsPanel settings={settings} onChange={onSettingsChange} providerBindings={providerBindings} />
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="node" className="mt-0 flex-1 overflow-hidden">
          <ScrollArea className="h-full px-3 pb-3">
            <div className="space-y-4 py-3">
              {selectedNode ? (
                <NodeConfigPanel
                  node={selectedNode}
                  onUpdate={onNodeUpdate}
                  onClose={onClearSelectedNode}
                  embedded
                />
              ) : (
                <div className="rounded-xl border border-dashed bg-muted/20 p-6 text-center">
                  <h3 className="text-sm font-semibold">Select a node to edit</h3>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Click any node on the canvas to configure prompts, conditions, transfer actions, and other details.
                  </p>
                </div>
              )}
            </div>
          </ScrollArea>
        </TabsContent>

        <TabsContent value="test" className="mt-0 flex-1 overflow-hidden">
          <ScrollArea className="h-full px-3 pb-3">
            <div className="space-y-4 py-3">
              <div className="rounded-xl border bg-muted/20 p-4">
                <h3 className="text-sm font-semibold">Test Agent</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Run a browser test call and review the live transcript without leaving the editor.
                </p>
              </div>
              <TestCallPanel agentId={agentId} />
              <PhoneTestCall agentId={agentId} />
            </div>
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </div>
  );
}