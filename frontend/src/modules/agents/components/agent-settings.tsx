"use client";

/**
 * Agent Settings UI — Comprehensive configuration for voice AI agents.
 *
 * Covers ALL PRD §3.4 settings:
 * - Voice & Language
 * - LLM Settings
 * - Knowledge Base Integration
 * - Speech Settings
 * - Transcription Settings
 * - Call Behavior
 * - Post-Call Data Extraction
 * - Webhooks
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ArrowRight,
  BookOpen,
  Brain,
  Check,
  Database,
  Languages,
  Loader2,
  Mic,
  Phone,
  Play,
  Plus,
  Search,
  Settings2,
  Sparkles,
  Square,
  Trash2,
  Volume2,
  Webhook,
  X,
} from "lucide-react";
import {
  useKnowledgeBases,
  useAgentKnowledgeBases,
  useAttachKBToAgent,
  useDetachKBFromAgent,
  type KnowledgeBase,
} from "@/modules/knowledge-base";
import { fetchWithAuth } from "@/lib/api-client";
import {
  useAgentPromptVariables,
  useCrmModuleFields,
} from "@/modules/campaigns/hooks/use-campaigns";

// ── Types ───────────────────────────────────────────────────

export interface VoiceLanguageSettings {
  language: string;
  ttsProvider: string;
  ttsModel: string;
  voiceId: string;
  voiceSpeed: number;
  voiceVolume: number;
  dynamicSpeedAdjustment: boolean;
}

export interface LLMSettings {
  provider: string;
  model: string;
  temperature: number;
  structuredOutput: boolean;
  maxTokens: number;
}

export interface KnowledgeBaseSettings {
  attachedKbIds: string[];
  chunkCount: number;
  similarityThreshold: number;
}

export interface LatencyTuningSettings {
  vadStopSecs: number;
  vadStartSecs: number;
  minVolume: number;
  confidence: number;
  speechTimeoutSecs: number;
}

export interface SpeechSettings {
  backgroundSound: string;
  backgroundSoundVolume: number;
  responsiveness: number;
  pronunciationGuide: Array<{ word: string; phonetic: string }>;
  latencyTuning: LatencyTuningSettings;
}

export type DenoisingMode = "noise_only" | "noise_and_speech" | "no_denoising";

export interface TranscriptionSettings {
  sttProvider: string;
  sttModel: string;
  /** @deprecated Use denoisingMode instead */
  denoisingEnabled?: boolean;
  denoisingMode: DenoisingMode;
  optimizeFor: "speed" | "accuracy";
  vocabularySpecialization: string;
  boostedKeywords: string[];
}

export interface CallBehaviorSettings {
  voicemailDetection: "hang_up" | "leave_message" | "disabled";
  ivrDetection: boolean;
  endOnSilenceSeconds: number;
  maxCallDurationMinutes: number;
  ringDurationSeconds: number;
}

export interface ExtractionField {
  name: string;
  type: "string" | "boolean" | "number" | "integer" | "array" | "object";
  description: string;
  options?: string[];
}

export interface PostCallExtractionSettings {
  enabled: boolean;
  defaults: {
    callSummary: boolean;
    successEvaluation: boolean;
    customerSentiment: boolean;
    customerFrustrated: boolean;
    agentPerformance: boolean;
    actionItems: boolean;
    callerInfo: boolean;
    [key: string]: boolean;
  };
  enabledCategories: string[];
  disabledFields: string[];
  customFields: ExtractionField[];
}

export interface WebhookSettings {
  url: string;
  events: string[];
  timeoutMs: number;
  retryCount: number;
  enabled: boolean;
}

export interface CrmWritebackSettings {
  enabled: boolean;
  crmModule: string;
  mapping: Record<string, string>;
  autoMapDefaults: boolean;
}

export interface AgentSettings {
  voiceLanguage: VoiceLanguageSettings;
  llm: LLMSettings;
  knowledgeBase: KnowledgeBaseSettings;
  speech: SpeechSettings;
  transcription: TranscriptionSettings;
  callBehavior: CallBehaviorSettings;
  postCallExtraction: PostCallExtractionSettings;
  webhooks: WebhookSettings;
  crmWriteback: CrmWritebackSettings;
}

export interface AgentProviderOption {
  value: string;
  label: string;
}

export interface AgentProviderBindings {
  sttProviders: AgentProviderOption[];
  sttModels: AgentProviderOption[];
  llmProviders: AgentProviderOption[];
  ttsProviders: AgentProviderOption[];
  ttsModels: AgentProviderOption[];
  ttsVoices: AgentProviderOption[];
  llmModels: AgentProviderOption[];
}

export interface AgentSettingsProps {
  settings: AgentSettings;
  onChange: (settings: AgentSettings) => void;
  readOnly?: boolean;
  providerBindings?: AgentProviderBindings;
  agentId?: string;
  /** Optional slot to render FunctionCallingConfig inside the Behavior tab */
  functionsSlot?: React.ReactNode;
}

// ── Constants ───────────────────────────────────────────────

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "hi", label: "Hindi" },
  { value: "bn", label: "Bengali" },
  { value: "gu", label: "Gujarati" },
  { value: "kn", label: "Kannada" },
  { value: "ml", label: "Malayalam" },
  { value: "mr", label: "Marathi" },
  { value: "or", label: "Odia" },
  { value: "pa", label: "Punjabi" },
  { value: "ta", label: "Tamil" },
  { value: "te", label: "Telugu" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" },
  { value: "zh", label: "Chinese (Mandarin)" },
  { value: "ar", label: "Arabic" },
];

const TTS_PROVIDERS = [
  { value: "cartesia", label: "Cartesia (Sonic-3)" },
  { value: "elevenlabs", label: "ElevenLabs (Turbo v2.5)" },
  { value: "sarvam", label: "Sarvam (Bulbul)" },
  { value: "groq_tts", label: "Groq TTS (Orpheus)" },
  { value: "inworld", label: "Inworld" },
  { value: "openai", label: "OpenAI TTS" },
  { value: "smallest", label: "Smallest AI (Lightning)" },
  { value: "lmnt", label: "LMNT" },
  { value: "azure", label: "Azure Speech" },
];

const LLM_MODELS = [
  { value: "groq/meta-llama/llama-4-scout-17b-16e-instruct", label: "Groq — Llama 4 Scout 17B", provider: "groq" },
  { value: "groq/openai/gpt-oss-120b", label: "Groq — GPT-OSS 120B", provider: "groq" },
  { value: "groq/llama-3.3-70b-versatile", label: "Groq — Llama 3.3 70B", provider: "groq" },
  { value: "groq/llama-3.1-8b-instant", label: "Groq — Llama 3.1 8B (fast)", provider: "groq" },
  { value: "openai/gpt-4o", label: "OpenAI — GPT-4o", provider: "openai" },
  { value: "openai/gpt-4o-mini", label: "OpenAI — GPT-4o Mini", provider: "openai" },
  { value: "anthropic/claude-sonnet-4-20250514", label: "Anthropic — Claude Sonnet 4", provider: "anthropic" },
  { value: "anthropic/claude-3-5-haiku-20241022", label: "Anthropic — Claude 3.5 Haiku", provider: "anthropic" },
];

const BACKGROUND_SOUNDS = [
  { value: "none", label: "None" },
  { value: "call_center", label: "Call Center" },
  { value: "coffee_shop", label: "Coffee Shop" },
  { value: "convention_hall", label: "Convention Hall" },
  { value: "keyboard_typing", label: "Keyboard Typing" },
  { value: "mountain_outdoor", label: "Mountain Outdoor" },
  { value: "static_noise", label: "Static Noise" },
  { value: "summer_outdoor", label: "Summer Outdoor" },
];

const VOCABULARY_SPECIALIZATIONS = [
  { value: "general", label: "General" },
  { value: "medical", label: "Medical" },
  { value: "legal", label: "Legal" },
  { value: "finance", label: "Finance" },
  { value: "technology", label: "Technology" },
];

const WEBHOOK_EVENTS = [
  { value: "call_started", label: "Call Started" },
  { value: "call_ended", label: "Call Ended" },
  { value: "call_failed", label: "Call Failed" },
  { value: "transcription_updated", label: "Transcription Updated" },
  { value: "extraction_completed", label: "Extraction Completed" },
  { value: "agent_transfer", label: "Agent Transfer" },
  { value: "dtmf_received", label: "DTMF Received" },
  { value: "voicemail_detected", label: "Voicemail Detected" },
];

// ── Default Settings Factory ────────────────────────────────

export function createDefaultSettings(): AgentSettings {
  return {
    voiceLanguage: {
      language: "en",
      ttsProvider: "",
      ttsModel: "",
      voiceId: "",
      voiceSpeed: 1.0,
      voiceVolume: 1.0,
      dynamicSpeedAdjustment: false,
    },
    llm: {
      provider: "",
      model: "",
      temperature: 0.7,
      structuredOutput: false,
      maxTokens: 1024,
    },
    knowledgeBase: {
      attachedKbIds: [],
      chunkCount: 5,
      similarityThreshold: 0.25,
    },
    speech: {
      backgroundSound: "none",
      backgroundSoundVolume: 0.15,
      responsiveness: 0.5,
      pronunciationGuide: [],
      latencyTuning: {
        vadStopSecs: 0.15,
        vadStartSecs: 0.15,
        minVolume: 0.5,
        confidence: 0.7,
        speechTimeoutSecs: 0.4,
      },
    },
    transcription: {
      sttProvider: "",
      sttModel: "",
      denoisingMode: "noise_only",
      optimizeFor: "speed",
      vocabularySpecialization: "general",
      boostedKeywords: [],
    },
    callBehavior: {
      voicemailDetection: "hang_up",
      ivrDetection: false,
      endOnSilenceSeconds: 8,
      maxCallDurationMinutes: 4,
      ringDurationSeconds: 30,
    },
    postCallExtraction: {
      enabled: true,
      defaults: {
        callSummary: true,
        successEvaluation: true,
        customerSentiment: true,
        customerFrustrated: true,
        agentPerformance: true,
        actionItems: true,
        callerInfo: true,
      },
      enabledCategories: [],
      disabledFields: [],
      customFields: [],
    },
    webhooks: {
      url: "",
      events: ["call_started", "call_ended"],
      timeoutMs: 5000,
      retryCount: 3,
      enabled: false,
    },
    crmWriteback: {
      enabled: false,
      crmModule: "",
      mapping: {},
      autoMapDefaults: false,
    },
  };
}

// ── Grouped Setting Panels (exported for page-level tabs) ───

export function VoiceSettingsGroup({
  settings,
  onChange,
  readOnly = false,
  providerBindings,
  onForceTranslate,
  isTranslating,
}: {
  settings: AgentSettings;
  onChange: (settings: AgentSettings) => void;
  readOnly?: boolean;
  providerBindings?: AgentProviderBindings;
  onForceTranslate?: () => void;
  isTranslating?: boolean;
}) {
  const update = useCallback(
    <K extends keyof AgentSettings>(section: K, patch: Partial<AgentSettings[K]>) => {
      onChange({ ...settings, [section]: { ...settings[section], ...patch } });
    },
    [settings, onChange],
  );

  return (
    <div className="space-y-8">
      <VoiceLanguageTab
        settings={settings.voiceLanguage}
        onChange={(patch) => update("voiceLanguage", patch)}
        readOnly={readOnly}
        providerBindings={providerBindings}
        onForceTranslate={onForceTranslate}
        isTranslating={isTranslating}
      />

      <Separator />
      <div className="flex items-center gap-2 text-sm font-medium">
        <Mic className="h-3.5 w-3.5 text-muted-foreground" />
        Audio &amp; Speech
      </div>
      <SpeechSettingsTab
        settings={settings.speech}
        onChange={(patch) => update("speech", patch)}
        readOnly={readOnly}
      />

      <Separator />
      <div className="flex items-center gap-2 text-sm font-medium">
        <Settings2 className="h-3.5 w-3.5 text-muted-foreground" />
        Transcription (STT)
      </div>
      <TranscriptionSettingsTab
        settings={settings.transcription}
        onChange={(patch) => update("transcription", patch)}
        readOnly={readOnly}
        providerBindings={providerBindings}
      />
    </div>
  );
}

export function ModelSettingsGroup({
  settings,
  onChange,
  readOnly = false,
  providerBindings,
  agentId,
  tenantId,
}: {
  settings: AgentSettings;
  onChange: (settings: AgentSettings) => void;
  readOnly?: boolean;
  providerBindings?: AgentProviderBindings;
  agentId?: string;
  tenantId?: string;
}) {
  const update = useCallback(
    <K extends keyof AgentSettings>(section: K, patch: Partial<AgentSettings[K]>) => {
      onChange({ ...settings, [section]: { ...settings[section], ...patch } });
    },
    [settings, onChange],
  );

  return (
    <div className="space-y-8">
      <LLMSettingsTab
        settings={settings.llm}
        onChange={(patch) => update("llm", patch)}
        readOnly={readOnly}
        providerBindings={providerBindings}
      />

      <Separator />
      <div className="flex items-center gap-2 text-sm font-medium">
        <BookOpen className="h-3.5 w-3.5 text-muted-foreground" />
        Knowledge Base
      </div>
      <KnowledgeBaseTab
        settings={settings.knowledgeBase}
        onChange={(patch) => update("knowledgeBase", patch)}
        readOnly={readOnly}
        agentId={agentId}
        tenantId={tenantId}
      />
    </div>
  );
}

export function BehaviorSettingsGroup({
  settings,
  onChange,
  readOnly = false,
  functionsSlot,
  agentId,
  tenantId,
  agentPrompt,
}: {
  settings: AgentSettings;
  onChange: (settings: AgentSettings) => void;
  readOnly?: boolean;
  functionsSlot?: React.ReactNode;
  agentId?: string;
  tenantId?: string;
  agentPrompt?: string;
}) {
  const update = useCallback(
    <K extends keyof AgentSettings>(section: K, patch: Partial<AgentSettings[K]>) => {
      onChange({ ...settings, [section]: { ...settings[section], ...patch } });
    },
    [settings, onChange],
  );

  return (
    <div className="space-y-8">
      {functionsSlot}

      <Separator />
      <div className="flex items-center gap-2 text-sm font-medium">
        <Phone className="h-3.5 w-3.5 text-muted-foreground" />
        Call Settings
      </div>
      <CallBehaviorTab
        settings={settings.callBehavior}
        onChange={(patch) => update("callBehavior", patch)}
        readOnly={readOnly}
      />

      <Separator />
      <div className="flex items-center gap-2 text-sm font-medium">
        <Settings2 className="h-3.5 w-3.5 text-muted-foreground" />
        Post-Call Extraction
      </div>
      <PostCallExtractionTab
        settings={settings.postCallExtraction}
        onChange={(patch) => update("postCallExtraction", patch)}
        readOnly={readOnly}
        agentPrompt={agentPrompt}
      />

      <Separator />
      <div className="flex items-center gap-2 text-sm font-medium">
        <Webhook className="h-3.5 w-3.5 text-muted-foreground" />
        Webhooks
      </div>
      <WebhookSettingsTab
        settings={settings.webhooks}
        onChange={(patch) => update("webhooks", patch)}
        readOnly={readOnly}
      />
    </div>
  );
}

// ── Voice & Language Tab ────────────────────────────────────

function VoiceLanguageTab({
  settings,
  onChange,
  readOnly,
  providerBindings,
  onForceTranslate,
  isTranslating,
}: {
  settings: VoiceLanguageSettings;
  onChange: (patch: Partial<VoiceLanguageSettings>) => void;
  readOnly: boolean;
  providerBindings?: AgentProviderBindings;
  onForceTranslate?: () => void;
  isTranslating?: boolean;
}) {
  const ttsProviders = providerBindings?.ttsProviders.length ? providerBindings.ttsProviders : TTS_PROVIDERS;
  const ttsModels = providerBindings?.ttsModels ?? [];
  const voiceOptions = providerBindings?.ttsVoices ?? [];

  return (
    <div className="space-y-5">
      {/* Language */}
      <div className="space-y-2">
        <Label htmlFor="language">Language</Label>
        <div className="flex items-center gap-2">
          <Select
            value={settings.language}
            onValueChange={(v) => onChange({ language: v })}
            disabled={readOnly}
          >
            <SelectTrigger id="language" className="flex-1">
              <SelectValue placeholder="Select language" />
            </SelectTrigger>
            <SelectContent>
              {LANGUAGES.map((lang) => (
                <SelectItem key={lang.value} value={lang.value}>
                  {lang.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {onForceTranslate && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onForceTranslate}
              disabled={readOnly || isTranslating}
              className="shrink-0"
            >
              {isTranslating ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <Languages className="mr-1.5 h-3.5 w-3.5" />
              )}
              Translate
            </Button>
          )}
        </div>
      </div>

      {/* TTS Provider */}
      <div className="space-y-2">
        <Label htmlFor="tts-provider">TTS Provider</Label>
        <Select
          value={settings.ttsProvider || undefined}
          onValueChange={(v) => onChange({ ttsProvider: v })}
          disabled={readOnly}
        >
          <SelectTrigger id="tts-provider">
            <SelectValue placeholder="Select TTS provider" />
          </SelectTrigger>
          <SelectContent>
            {ttsProviders.map((p) => (
              <SelectItem key={p.value} value={p.value}>
                {p.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="tts-model">TTS Model</Label>
        {ttsModels.length > 0 ? (
          <Select
            value={settings.ttsModel || undefined}
            onValueChange={(value) => onChange({ ttsModel: value })}
            disabled={readOnly}
          >
            <SelectTrigger id="tts-model">
              <SelectValue placeholder="Select a synced TTS model" />
            </SelectTrigger>
            <SelectContent>
              {ttsModels.map((model) => (
                <SelectItem key={model.value} value={model.value}>
                  {model.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            id="tts-model"
            value={settings.ttsModel}
            onChange={(event) => onChange({ ttsModel: event.target.value })}
            placeholder="Enter TTS model from provider"
            readOnly={readOnly}
          />
        )}
        <p className="text-xs text-muted-foreground">
          {ttsModels.length > 0
            ? "TTS model choices are coming from the synced provider catalog."
            : "Model identifier from the selected TTS provider."}
        </p>
      </div>

      {/* Voice ID */}
      <div className="space-y-2">
        <Label htmlFor="voice-id">Voice ID</Label>
        {voiceOptions.length > 0 ? (
          <Select
            value={settings.voiceId || undefined}
            onValueChange={(value) => onChange({ voiceId: value })}
            disabled={readOnly}
          >
            <SelectTrigger id="voice-id">
              <SelectValue placeholder="Select a synced voice" />
            </SelectTrigger>
            <SelectContent>
              {voiceOptions.map((voice) => (
                <SelectItem key={voice.value} value={voice.value}>
                  {voice.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            id="voice-id"
            value={settings.voiceId}
            onChange={(e) => onChange({ voiceId: e.target.value })}
            placeholder="Enter voice ID from provider"
            readOnly={readOnly}
          />
        )}
        <p className="text-xs text-muted-foreground">
          {voiceOptions.length > 0
            ? "Voice choices are coming from the synced provider catalog."
            : "Voice identifier from the selected TTS provider."}
        </p>
      </div>

      {/* Voice Speed */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Voice Speed</Label>
          <span className="text-sm font-medium">{settings.voiceSpeed.toFixed(1)}x</span>
        </div>
        <Slider
          value={[settings.voiceSpeed]}
          onValueChange={([v]) => onChange({ voiceSpeed: v })}
          min={0.5}
          max={2.0}
          step={0.1}
          disabled={readOnly}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>0.5x</span>
          <span>1.0x (normal)</span>
          <span>2.0x</span>
        </div>
      </div>

      {/* Voice Volume */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Voice Volume</Label>
          <span className="text-sm font-medium">{Math.round(settings.voiceVolume * 100)}%</span>
        </div>
        <Slider
          value={[settings.voiceVolume]}
          onValueChange={([v]) => onChange({ voiceVolume: v })}
          min={0.1}
          max={1.5}
          step={0.05}
          disabled={readOnly}
        />
      </div>

      {/* Dynamic Speed Adjustment */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Dynamic Speed Adjustment</Label>
          <p className="text-xs text-muted-foreground">
            Automatically adjust speaking speed based on conversation context.
          </p>
        </div>
        <Switch
          checked={settings.dynamicSpeedAdjustment}
          onCheckedChange={(v) => onChange({ dynamicSpeedAdjustment: v })}
          disabled={readOnly}
        />
      </div>
    </div>
  );
}

// ── LLM Settings Tab ────────────────────────────────────────

function LLMSettingsTab({
  settings,
  onChange,
  readOnly,
  providerBindings,
}: {
  settings: LLMSettings;
  onChange: (patch: Partial<LLMSettings>) => void;
  readOnly: boolean;
  providerBindings?: AgentProviderBindings;
}) {
  const providerOptions = providerBindings?.llmProviders ?? [];
  const modelOptions = providerBindings?.llmModels.length ? providerBindings.llmModels : LLM_MODELS;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="llm-provider">Provider</Label>
        <Select
          value={settings.provider || undefined}
          onValueChange={(value) => onChange({ provider: value })}
          disabled={readOnly}
        >
          <SelectTrigger id="llm-provider">
            <SelectValue placeholder="Select LLM provider" />
          </SelectTrigger>
          <SelectContent>
            {providerOptions.map((provider) => (
              <SelectItem key={provider.value} value={provider.value}>
                {provider.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Model Selection */}
      <div className="space-y-2">
        <Label htmlFor="llm-model">Model</Label>
        <Select
          value={settings.model || undefined}
          onValueChange={(v) => onChange({ model: v })}
          disabled={readOnly}
        >
          <SelectTrigger id="llm-model">
            <SelectValue placeholder="Select model" />
          </SelectTrigger>
          <SelectContent>
            {modelOptions.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Temperature */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Temperature</Label>
          <span className="text-sm font-medium">{settings.temperature.toFixed(2)}</span>
        </div>
        <Slider
          value={[settings.temperature]}
          onValueChange={([v]) => onChange({ temperature: v })}
          min={0}
          max={2}
          step={0.05}
          disabled={readOnly}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Precise (0)</span>
          <span>Balanced (0.7)</span>
          <span>Creative (2.0)</span>
        </div>
      </div>

      {/* Max Tokens */}
      <div className="space-y-2">
        <Label htmlFor="max-tokens">Max Output Tokens</Label>
        <Input
          id="max-tokens"
          type="number"
          value={settings.maxTokens}
          onChange={(e) => onChange({ maxTokens: parseInt(e.target.value, 10) || 1024 })}
          min={64}
          max={16384}
          readOnly={readOnly}
        />
        <p className="text-xs text-muted-foreground">
          Maximum number of tokens in each LLM response (64–16384).
        </p>
      </div>

      {/* Structured Output */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Structured Output</Label>
          <p className="text-xs text-muted-foreground">
            Enforce JSON responses from the LLM. Useful for function calls.
          </p>
        </div>
        <Switch
          checked={settings.structuredOutput}
          onCheckedChange={(v) => onChange({ structuredOutput: v })}
          disabled={readOnly}
        />
      </div>
    </div>
  );
}

// ── Knowledge Base Tab ──────────────────────────────────────

function KnowledgeBaseTab({
  settings,
  onChange,
  readOnly,
  agentId,
  tenantId,
}: {
  settings: KnowledgeBaseSettings;
  onChange: (patch: Partial<KnowledgeBaseSettings>) => void;
  readOnly: boolean;
  agentId?: string;
  tenantId?: string;
}) {
  const [pickerOpen, setPickerOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const { data: kbListData, isLoading: kbLoading } = useKnowledgeBases({
    pageSize: 50,
    search: searchQuery || undefined,
    tenantId: tenantId,
  });
  const { data: attachedKbs } = useAgentKnowledgeBases(agentId ?? "");
  const attachMutation = useAttachKBToAgent(agentId ?? "");
  const detachMutation = useDetachKBFromAgent(agentId ?? "");

  const availableKbs = kbListData?.items ?? [];

  // Derive attached IDs from the join table when available, fall back to JSONB
  const attachedIds = attachedKbs ? attachedKbs.map((kb) => kb.kb_id) : settings.attachedKbIds;
  const attachedSet = new Set(attachedIds);

  // KB metadata map — used to display names instead of raw UUIDs
  const kbMap = new Map<string, KnowledgeBase>();
  for (const kb of availableKbs) {
    kbMap.set(kb.id, kb);
  }
  // Merge names from join table response
  if (attachedKbs) {
    for (const link of attachedKbs) {
      if (!kbMap.has(link.kb_id)) {
        kbMap.set(link.kb_id, { id: link.kb_id, name: link.kb_name } as KnowledgeBase);
      }
    }
  }

  const handleToggleKb = (kbId: string) => {
    if (attachedSet.has(kbId)) {
      // Detach
      if (agentId) {
        detachMutation.mutate(kbId, {
          onSuccess: () => {
            onChange({ attachedKbIds: attachedIds.filter((id) => id !== kbId) });
          },
        });
      } else {
        onChange({ attachedKbIds: settings.attachedKbIds.filter((id) => id !== kbId) });
      }
    } else {
      // Attach
      if (agentId) {
        attachMutation.mutate(
          {
            kb_id: kbId,
            chunk_count: settings.chunkCount,
            similarity_threshold: settings.similarityThreshold,
          },
          {
            onSuccess: () => {
              onChange({ attachedKbIds: [...attachedIds, kbId] });
            },
          },
        );
      } else {
        onChange({ attachedKbIds: [...settings.attachedKbIds, kbId] });
      }
    }
  };

  const handleRemoveKb = (kbId: string) => {
    if (agentId) {
      detachMutation.mutate(kbId, {
        onSuccess: () => {
          onChange({ attachedKbIds: attachedIds.filter((id) => id !== kbId) });
        },
      });
    } else {
      onChange({ attachedKbIds: settings.attachedKbIds.filter((id) => id !== kbId) });
    }
  };

  return (
    <div className="space-y-5">
      {/* Attached KBs */}
      <div className="space-y-2">
        <Label>Attached Knowledge Bases</Label>
        {attachedIds.length === 0 ? (
          <div className="rounded-lg border border-dashed p-4 text-center text-sm text-muted-foreground">
            No knowledge bases attached. Attach one to enable RAG during calls.
          </div>
        ) : (
          <div className="space-y-2">
            {attachedIds.map((id) => {
              const kb = kbMap.get(id);
              return (
                <div key={id} className="flex items-center justify-between rounded-lg border p-2 px-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <BookOpen className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">
                        {kb?.name ?? id}
                      </p>
                      {kb && (
                        <p className="text-xs text-muted-foreground">
                          {kb.document_count} doc{kb.document_count !== 1 ? "s" : ""} · {kb.sharing_scope}
                        </p>
                      )}
                    </div>
                  </div>
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0 shrink-0"
                      onClick={() => handleRemoveKb(id)}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}
        {!readOnly && (
          <Button
            variant="outline"
            size="sm"
            className="mt-2 gap-1"
            onClick={() => setPickerOpen(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            Attach Knowledge Base
          </Button>
        )}

        {/* KB Picker Dialog */}
        <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Attach Knowledge Bases</DialogTitle>
              <DialogDescription>
                Select knowledge bases to attach to this agent for RAG during calls.
              </DialogDescription>
            </DialogHeader>

            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search knowledge bases..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9"
              />
            </div>

            {/* KB List */}
            <ScrollArea className="max-h-64">
              {kbLoading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                </div>
              ) : availableKbs.length === 0 ? (
                <div className="py-8 text-center text-sm text-muted-foreground">
                  {searchQuery
                    ? "No knowledge bases match your search."
                    : "No knowledge bases available. Create one first."}
                </div>
              ) : (
                <div className="space-y-1">
                  {availableKbs.map((kb) => {
                    const isAttached = attachedSet.has(kb.id);
                    return (
                      <button
                        key={kb.id}
                        type="button"
                        className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left transition-colors hover:bg-accent ${isAttached ? "bg-accent/50" : ""
                          }`}
                        onClick={() => handleToggleKb(kb.id)}
                      >
                        <div
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${isAttached
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-muted-foreground/30"
                            }`}
                        >
                          {isAttached && <Check className="h-3 w-3" />}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium truncate">{kb.name}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {kb.document_count} doc{kb.document_count !== 1 ? "s" : ""} · {kb.sharing_scope}
                            {kb.description ? ` · ${kb.description}` : ""}
                          </p>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </ScrollArea>

            <DialogFooter>
              <Button variant="outline" onClick={() => setPickerOpen(false)}>
                Done
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

// ── Speech Settings Tab ─────────────────────────────────────

// Maps sound key → public asset path
const SOUND_PREVIEW_URL: Record<string, string> = {
  call_center: "/ambient/Call Center.mp3",
  coffee_shop: "/ambient/Coffee Shop.mp3",
  convention_hall: "/ambient/Convention hall.mp3",
  keyboard_typing: "/ambient/Keyboard Typing.mp3",
  mountain_outdoor: "/ambient/Mountain Outdoor.mp3",
  static_noise: "/ambient/Static Noise.mp3",
  summer_outdoor: "/ambient/Summer Outdoor.mp3",
};

function SpeechSettingsTab({
  settings,
  onChange,
  readOnly,
}: {
  settings: SpeechSettings;
  onChange: (patch: Partial<SpeechSettings>) => void;
  readOnly: boolean;
}) {
  const [newWord, setNewWord] = useState("");
  const [newPhonetic, setNewPhonetic] = useState("");
  const [previewing, setPreviewing] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Stop preview when sound selection changes
  useEffect(() => {
    stopPreview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.backgroundSound]);

  // Cleanup on unmount
  useEffect(() => () => stopPreview(), []);

  function stopPreview() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
      audioRef.current = null;
    }
    setPreviewing(false);
  }

  function togglePreview() {
    if (previewing) {
      stopPreview();
      return;
    }
    const url = SOUND_PREVIEW_URL[settings.backgroundSound];
    if (!url) return;
    const audio = new Audio(url);
    audio.loop = true;
    audio.volume = settings.backgroundSoundVolume ?? 0.15;
    audio.play().catch(() => { });
    audio.addEventListener("ended", stopPreview);
    audioRef.current = audio;
    setPreviewing(true);
  }

  const addPronunciation = () => {
    if (newWord.trim() && newPhonetic.trim()) {
      onChange({
        pronunciationGuide: [
          ...settings.pronunciationGuide,
          { word: newWord.trim(), phonetic: newPhonetic.trim() },
        ],
      });
      setNewWord("");
      setNewPhonetic("");
    }
  };

  return (
    <div className="space-y-5">
      {/* Background Sound */}
      <div className="space-y-2">
        <Label>Background Sound</Label>
        <div className="flex gap-2">
          <Select
            value={settings.backgroundSound}
            onValueChange={(v) => onChange({ backgroundSound: v })}
            disabled={readOnly}
          >
            <SelectTrigger className="flex-1">
              <SelectValue placeholder="Select background sound" />
            </SelectTrigger>
            <SelectContent>
              {BACKGROUND_SOUNDS.map((s) => (
                <SelectItem key={s.value} value={s.value}>
                  {s.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {settings.backgroundSound !== "none" && (
            <Button
              type="button"
              variant={previewing ? "default" : "outline"}
              size="icon"
              onClick={togglePreview}
              title={previewing ? "Stop preview" : "Preview sound"}
            >
              {previewing ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
            </Button>
          )}
        </div>
      </div>

      {/* Background Sound Volume — only shown when a sound is selected */}
      {settings.backgroundSound !== "none" && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Background Volume</Label>
            <span className="text-sm font-medium">{Math.round((settings.backgroundSoundVolume ?? 0.15) * 100)}%</span>
          </div>
          <Slider
            value={[settings.backgroundSoundVolume ?? 0.15]}
            onValueChange={([v]) => {
              onChange({ backgroundSoundVolume: v });
              // Update live preview volume in real-time
              if (audioRef.current) audioRef.current.volume = v;
            }}
            min={0.05}
            max={0.5}
            step={0.05}
            disabled={readOnly}
          />
          <div className="flex justify-between text-xs text-muted-foreground">
            <span>Subtle</span>
            <span>Prominent</span>
          </div>
        </div>
      )}

      {/* Responsiveness */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Responsiveness</Label>
          <span className="text-sm font-medium">{settings.responsiveness.toFixed(1)}</span>
        </div>
        <Slider
          value={[settings.responsiveness]}
          onValueChange={([v]) => onChange({ responsiveness: v })}
          min={0}
          max={1}
          step={0.1}
          disabled={readOnly}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Patient (waits longer)</span>
          <span>Responsive (interrupts quickly)</span>
        </div>
      </div>

      <Separator />

      {/* Latency Tuning */}
      <div className="space-y-4">
        <div>
          <Label className="flex items-center gap-2">
            <Settings2 className="h-4 w-4" />
            Latency Tuning
          </Label>
          <p className="text-xs text-muted-foreground mt-1">
            Fine-tune VAD and turn-taking for ultra-low latency. Lower = faster response, but may cut off mid-sentence.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">VAD Stop (s)</Label>
            <Input
              type="number"
              step={0.05}
              min={0.05}
              max={1.0}
              value={settings.latencyTuning?.vadStopSecs ?? 0.15}
              onChange={(e) =>
                onChange({
                  latencyTuning: {
                    ...(settings.latencyTuning ?? { vadStopSecs: 0.15, vadStartSecs: 0.15, minVolume: 0.5, confidence: 0.7, speechTimeoutSecs: 0.4 }),
                    vadStopSecs: parseFloat(e.target.value) || 0.15,
                  },
                })
              }
              disabled={readOnly}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">VAD Start (s)</Label>
            <Input
              type="number"
              step={0.05}
              min={0.05}
              max={1.0}
              value={settings.latencyTuning?.vadStartSecs ?? 0.15}
              onChange={(e) =>
                onChange({
                  latencyTuning: {
                    ...(settings.latencyTuning ?? { vadStopSecs: 0.15, vadStartSecs: 0.15, minVolume: 0.5, confidence: 0.7, speechTimeoutSecs: 0.4 }),
                    vadStartSecs: parseFloat(e.target.value) || 0.15,
                  },
                })
              }
              disabled={readOnly}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Min Volume</Label>
            <Input
              type="number"
              step={0.05}
              min={0.0}
              max={1.0}
              value={settings.latencyTuning?.minVolume ?? 0.5}
              onChange={(e) =>
                onChange({
                  latencyTuning: {
                    ...(settings.latencyTuning ?? { vadStopSecs: 0.15, vadStartSecs: 0.15, minVolume: 0.5, confidence: 0.7, speechTimeoutSecs: 0.4 }),
                    minVolume: parseFloat(e.target.value) || 0.5,
                  },
                })
              }
              disabled={readOnly}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Confidence</Label>
            <Input
              type="number"
              step={0.05}
              min={0.0}
              max={1.0}
              value={settings.latencyTuning?.confidence ?? 0.7}
              onChange={(e) =>
                onChange({
                  latencyTuning: {
                    ...(settings.latencyTuning ?? { vadStopSecs: 0.15, vadStartSecs: 0.15, minVolume: 0.5, confidence: 0.7, speechTimeoutSecs: 0.4 }),
                    confidence: parseFloat(e.target.value) || 0.7,
                  },
                })
              }
              disabled={readOnly}
            />
          </div>
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Speech Timeout (s)</Label>
          <Input
            type="number"
            step={0.05}
            min={0.1}
            max={2.0}
            value={settings.latencyTuning?.speechTimeoutSecs ?? 0.4}
            onChange={(e) =>
              onChange({
                latencyTuning: {
                  ...(settings.latencyTuning ?? { vadStopSecs: 0.15, vadStartSecs: 0.15, minVolume: 0.5, confidence: 0.7, speechTimeoutSecs: 0.4 }),
                  speechTimeoutSecs: parseFloat(e.target.value) || 0.4,
                },
              })
            }
            disabled={readOnly}
          />
          <p className="text-xs text-muted-foreground">
            Lower = faster response, but may cut off mid-sentence
          </p>
        </div>
      </div>

      <Separator />

      {/* Pronunciation Guide */}
      <div className="space-y-3">
        <Label>Pronunciation Guide</Label>
        <p className="text-xs text-muted-foreground">
          Define custom phonetics for brand names and technical terms.
        </p>
        {settings.pronunciationGuide.length > 0 && (
          <ScrollArea className="max-h-[200px]">
            <div className="space-y-2">
              {settings.pronunciationGuide.map((entry, idx) => (
                <div key={idx} className="flex items-center gap-2 rounded border p-2">
                  <span className="text-sm font-medium">{entry.word}</span>
                  <span className="text-xs text-muted-foreground">→</span>
                  <span className="text-sm font-mono text-muted-foreground">
                    {entry.phonetic}
                  </span>
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="ml-auto h-6 w-6 p-0"
                      onClick={() =>
                        onChange({
                          pronunciationGuide: settings.pronunciationGuide.filter(
                            (_, i) => i !== idx
                          ),
                        })
                      }
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
        {!readOnly && (
          <div className="flex items-end gap-2">
            <div className="flex-1 space-y-1">
              <Label className="text-xs">Word</Label>
              <Input
                value={newWord}
                onChange={(e) => setNewWord(e.target.value)}
                placeholder="e.g., Sphere"
                className="h-8"
              />
            </div>
            <div className="flex-1 space-y-1">
              <Label className="text-xs">Phonetic</Label>
              <Input
                value={newPhonetic}
                onChange={(e) => setNewPhonetic(e.target.value)}
                placeholder="e.g., Go-rill-ah"
                className="h-8"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              className="h-8"
              onClick={addPronunciation}
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Transcription Settings Tab ──────────────────────────────

function TranscriptionSettingsTab({
  settings,
  onChange,
  readOnly,
  providerBindings,
}: {
  settings: TranscriptionSettings;
  onChange: (patch: Partial<TranscriptionSettings>) => void;
  readOnly: boolean;
  providerBindings?: AgentProviderBindings;
}) {
  const [newKeyword, setNewKeyword] = useState("");
  const sttProviders = providerBindings?.sttProviders ?? [];
  const sttModels = providerBindings?.sttModels ?? [];

  const addKeyword = () => {
    const word = newKeyword.trim();
    if (word && !settings.boostedKeywords.includes(word)) {
      onChange({ boostedKeywords: [...settings.boostedKeywords, word] });
      setNewKeyword("");
    }
  };

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Label htmlFor="stt-provider">STT Provider</Label>
        <Select
          value={settings.sttProvider || undefined}
          onValueChange={(value) => onChange({ sttProvider: value })}
          disabled={readOnly}
        >
          <SelectTrigger id="stt-provider">
            <SelectValue placeholder="Select STT provider" />
          </SelectTrigger>
          <SelectContent>
            {sttProviders.map((provider) => (
              <SelectItem key={provider.value} value={provider.value}>
                {provider.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="stt-model">STT Model</Label>
        {sttModels.length > 0 ? (
          <Select
            value={settings.sttModel || undefined}
            onValueChange={(value) => onChange({ sttModel: value })}
            disabled={readOnly}
          >
            <SelectTrigger id="stt-model">
              <SelectValue placeholder="Select a synced STT model" />
            </SelectTrigger>
            <SelectContent>
              {sttModels.map((model) => (
                <SelectItem key={model.value} value={model.value}>
                  {model.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        ) : (
          <Input
            id="stt-model"
            value={settings.sttModel}
            onChange={(event) => onChange({ sttModel: event.target.value })}
            placeholder="Enter STT model from provider"
            readOnly={readOnly}
          />
        )}
        <p className="text-xs text-muted-foreground">
          {sttModels.length > 0
            ? "STT model choices are coming from the synced provider catalog."
            : "Model identifier from the selected STT provider."}
        </p>
      </div>

      {settings.sttProvider === "groq_whisper" && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
          Live browser and phone calls currently fall back to a realtime STT provider instead of Groq Whisper. Groq STT in the current Pipecat path is not true streaming STT, so using it directly stalls turn-taking.
        </div>
      )}

      {/* Denoising Mode */}
      <div className="space-y-2">
        <Label>Denoising Mode</Label>
        <p className="text-xs text-muted-foreground">
          Filter out unwanted background noise or speech.
        </p>
        <div className="space-y-1.5">
          {[
            { value: "noise_only" as const, label: "Remove noise" },
            { value: "noise_and_speech" as const, label: "Remove noise + background speech" },
            { value: "no_denoising" as const, label: "No denoising" },
          ].map((opt) => (
            <label
              key={opt.value}
              className="flex items-center gap-2 cursor-pointer text-sm"
            >
              <input
                type="radio"
                name="denoising-mode"
                value={opt.value}
                checked={(settings.denoisingMode ?? "noise_only") === opt.value}
                onChange={() => onChange({ denoisingMode: opt.value })}
                disabled={readOnly}
                className="accent-primary"
              />
              {opt.label}
            </label>
          ))}
        </div>
      </div>

      {settings.sttProvider === "deepgram" || settings.sttProvider === "deepgram_flux" || !settings.sttProvider ? (
        <div className="space-y-2">
          <Label>Optimize For</Label>
          <Select
            value={settings.optimizeFor}
            onValueChange={(v) => onChange({ optimizeFor: v as "speed" | "accuracy" })}
            disabled={readOnly}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="speed">Speed (Deepgram Flux)</SelectItem>
              <SelectItem value="accuracy">Accuracy (Deepgram Nova-3)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {/* Vocabulary Specialization */}
      <div className="space-y-2">
        <Label>Vocabulary Specialization</Label>
        <Select
          value={settings.vocabularySpecialization}
          onValueChange={(v) => onChange({ vocabularySpecialization: v })}
          disabled={readOnly}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {VOCABULARY_SPECIALIZATIONS.map((s) => (
              <SelectItem key={s.value} value={s.value}>
                {s.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Separator />

      {/* Boosted Keywords */}
      <div className="space-y-3">
        <Label>Boosted Keywords</Label>
        <p className="text-xs text-muted-foreground">
          Boost recognition of specific words and phrases.
        </p>
        {settings.boostedKeywords.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {settings.boostedKeywords.map((kw) => (
              <Badge key={kw} variant="secondary" className="gap-1">
                {kw}
                {!readOnly && (
                  <button
                    type="button"
                    onClick={() =>
                      onChange({
                        boostedKeywords: settings.boostedKeywords.filter((k) => k !== kw),
                      })
                    }
                    className="ml-0.5 rounded-full hover:bg-muted"
                  >
                    <X className="h-2.5 w-2.5" />
                  </button>
                )}
              </Badge>
            ))}
          </div>
        )}
        {!readOnly && (
          <div className="flex gap-2">
            <Input
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              placeholder="Add keyword..."
              className="h-8"
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addKeyword();
                }
              }}
            />
            <Button variant="outline" size="sm" className="h-8" onClick={addKeyword}>
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Call Behavior Tab ───────────────────────────────────────

/** Format seconds into human-readable duration (e.g. "30s", "2m", "5m 30s"). */
function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}m ${s}s` : `${m}m`;
}

function CallBehaviorTab({
  settings,
  onChange,
  readOnly,
}: {
  settings: CallBehaviorSettings;
  onChange: (patch: Partial<CallBehaviorSettings>) => void;
  readOnly: boolean;
}) {
  return (
    <div className="space-y-5">
      {/* Voicemail Detection */}
      <div className="space-y-2">
        <Label>Voicemail Detection</Label>
        <Select
          value={settings.voicemailDetection}
          onValueChange={(v) =>
            onChange({
              voicemailDetection: v as "hang_up" | "leave_message" | "disabled",
            })
          }
          disabled={readOnly}
        >
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="hang_up">Hang Up</SelectItem>
            <SelectItem value="leave_message">Leave Message</SelectItem>
            <SelectItem value="disabled">Disabled</SelectItem>
          </SelectContent>
        </Select>
        <p className="text-xs text-muted-foreground">
          What the agent does when voicemail is detected.
        </p>
      </div>

      {/* IVR Detection */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>IVR Detection</Label>
          <p className="text-xs text-muted-foreground">
            Hang up if an automated phone system (IVR) is detected.
          </p>
        </div>
        <Switch
          checked={settings.ivrDetection}
          onCheckedChange={(v) => onChange({ ivrDetection: v })}
          disabled={readOnly}
        />
      </div>

      <Separator />

      {/* ── Call Termination & Duration Settings ── */}

      {/* End on Silence */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>End Call on Silence</Label>
          <span className="text-sm font-medium">{formatDuration(settings.endOnSilenceSeconds)}</span>
        </div>
        <Slider
          value={[settings.endOnSilenceSeconds]}
          onValueChange={([v]) => onChange({ endOnSilenceSeconds: v })}
          min={5}
          max={1800}
          step={5}
          disabled={readOnly}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>5s</span>
          <span>30m</span>
        </div>
        <p className="text-xs text-muted-foreground">
          End the call if the user stays silent for this duration. The agent asks &quot;still there?&quot; first — call ends 5s later if no response.
        </p>
      </div>

      {/* Max Call Duration */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Max Call Duration</Label>
          <span className="text-sm font-medium">{settings.maxCallDurationMinutes} min</span>
        </div>
        <Slider
          value={[settings.maxCallDurationMinutes]}
          onValueChange={([v]) => onChange({ maxCallDurationMinutes: v })}
          min={1}
          max={120}
          step={1}
          disabled={readOnly}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>1 min</span>
          <span>2 hours</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Maximum allowed duration before automatic termination. Prevents runaway calls from accumulating charges.
        </p>
      </div>

      {/* Ring Duration */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Ring Duration</Label>
          <span className="text-sm font-medium">{settings.ringDurationSeconds}s</span>
        </div>
        <Slider
          value={[settings.ringDurationSeconds]}
          onValueChange={([v]) => onChange({ ringDurationSeconds: v })}
          min={5}
          max={300}
          step={5}
          disabled={readOnly}
        />
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>5s</span>
          <span>300s</span>
        </div>
        <p className="text-xs text-muted-foreground">
          Maximum ringing duration before the outbound or transfer call is considered unanswered.
        </p>
      </div>
    </div>
  );
}

// ── Post-Call Extraction Tab ────────────────────────────────

function PostCallExtractionTab({
  settings,
  onChange,
  readOnly,
  agentPrompt,
}: {
  settings: PostCallExtractionSettings;
  onChange: (patch: Partial<PostCallExtractionSettings>) => void;
  readOnly: boolean;
  agentPrompt?: string;
}) {
  const [fieldName, setFieldName] = useState("");
  const [fieldType, setFieldType] = useState<ExtractionField["type"]>("string");
  const [fieldDesc, setFieldDesc] = useState("");
  const [suggestedFields, setSuggestedFields] = useState<ExtractionField[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);

  const generateFieldSuggestions = async () => {
    if (!agentPrompt?.trim()) return;
    setIsGenerating(true);
    setShowSuggestions(true);
    try {
      const res = await fetchWithAuth("/api/v1/agents/ai/suggest-extraction-fields", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: agentPrompt }),
      });
      if (!res.ok) throw new Error("Failed to generate suggestions");
      const data = await res.json();
      // Filter out fields that already exist in customFields
      const existingNames = new Set((settings.customFields || []).map((f) => f.name));
      setSuggestedFields(
        (data.fields || []).filter((f: ExtractionField) => !existingNames.has(f.name))
      );
    } catch {
      setSuggestedFields([]);
    } finally {
      setIsGenerating(false);
    }
  };

  const addSuggestedField = (field: ExtractionField) => {
    onChange({
      customFields: [...(settings.customFields || []), field],
    });
    setSuggestedFields((prev) => prev.filter((f) => f.name !== field.name));
  };

  const addAllSuggestedFields = () => {
    onChange({
      customFields: [...(settings.customFields || []), ...suggestedFields],
    });
    setSuggestedFields([]);
    setShowSuggestions(false);
  };

  const [templates, setTemplates] = useState<Record<string, { label: string; icon: string; fields: Array<{ name: string; type: string; description: string }> }>>({});

  useEffect(() => {
    fetchWithAuth("/api/v1/pipeline/extraction-templates")
      .then((res) => (res.ok ? res.json() : { templates: {} }))
      .then((data: { templates?: Record<string, { label: string; icon: string; fields: Array<{ name: string; type: string; description: string }> }> }) => {
        setTemplates(data.templates ?? {});
      })
      .catch(() => { });
  }, []);

  const addField = () => {
    if (fieldName.trim() && fieldDesc.trim()) {
      onChange({
        customFields: [
          ...(settings.customFields || []),
          {
            name: fieldName.trim().toLowerCase().replace(/\s+/g, "_"),
            type: fieldType,
            description: fieldDesc.trim(),
          },
        ],
      });
      setFieldName("");
      setFieldDesc("");
      setFieldType("string");
    }
  };

  const enabledCategories = settings.enabledCategories || [];
  const disabledFields = settings.disabledFields || [];

  const toggleCategory = (categoryKey: string) => {
    const isEnabled = enabledCategories.includes(categoryKey);
    if (isEnabled) {
      const categoryFieldNames = templates[categoryKey]?.fields?.map((f) => f.name) ?? [];
      onChange({
        enabledCategories: enabledCategories.filter((c) => c !== categoryKey),
        disabledFields: disabledFields.filter((f) => !categoryFieldNames.includes(f)),
      });
    } else {
      onChange({
        enabledCategories: [...enabledCategories, categoryKey],
      });
    }
  };

  const toggleField = (fieldName: string) => {
    const isDisabled = disabledFields.includes(fieldName);
    if (isDisabled) {
      onChange({ disabledFields: disabledFields.filter((f) => f !== fieldName) });
    } else {
      onChange({ disabledFields: [...disabledFields, fieldName] });
    }
  };

  const getCategoryIcon = (iconName: string) => {
    const icons: Record<string, string> = {
      "heart-pulse": "🏥",
      building: "🏨",
      home: "🏠",
      "dollar-sign": "💰",
      headphones: "🎧",
      shield: "🛡",
      "clipboard-check": "📋",
      utensils: "🍽",
      calendar: "📅",
      smile: "😊",
    };
    return icons[iconName] || "📋";
  };

  return (
    <div className="space-y-5">
      {/* Master Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable Extraction</Label>
          <p className="text-xs text-muted-foreground">
            Run extraction after every call.
          </p>
        </div>
        <Switch
          checked={settings.enabled}
          onCheckedChange={(v) => onChange({ enabled: v })}
          disabled={readOnly}
        />
      </div>

      <Separator />

      {/* Default Fields */}
      <div className="space-y-3">
        <Label>Default Fields</Label>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Call Summary</p>
              <p className="text-xs text-muted-foreground">Summary, key topics, caller intent & outcome</p>
            </div>
            <Switch
              checked={settings.defaults?.callSummary ?? true}
              onCheckedChange={(v) => onChange({ defaults: { ...settings.defaults, callSummary: v } })}
              disabled={readOnly || !settings.enabled}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Success Evaluation</p>
              <p className="text-xs text-muted-foreground">Whether the call achieved its goal + score</p>
            </div>
            <Switch
              checked={settings.defaults?.successEvaluation ?? true}
              onCheckedChange={(v) => onChange({ defaults: { ...settings.defaults, successEvaluation: v } })}
              disabled={readOnly || !settings.enabled}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Customer Sentiment</p>
              <p className="text-xs text-muted-foreground">Sentiment analysis + frustration detection</p>
            </div>
            <Switch
              checked={settings.defaults?.customerSentiment ?? true}
              onCheckedChange={(v) => onChange({ defaults: { ...settings.defaults, customerSentiment: v } })}
              disabled={readOnly || !settings.enabled}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Agent Performance</p>
              <p className="text-xs text-muted-foreground">Script adherence, tone, and errors</p>
            </div>
            <Switch
              checked={settings.defaults?.agentPerformance ?? true}
              onCheckedChange={(v) => onChange({ defaults: { ...settings.defaults, agentPerformance: v } })}
              disabled={readOnly || !settings.enabled}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Action Items</p>
              <p className="text-xs text-muted-foreground">Follow-up actions and next steps</p>
            </div>
            <Switch
              checked={settings.defaults?.actionItems ?? true}
              onCheckedChange={(v) => onChange({ defaults: { ...settings.defaults, actionItems: v } })}
              disabled={readOnly || !settings.enabled}
            />
          </div>
          <div className="flex items-center justify-between rounded-lg border p-3">
            <div>
              <p className="text-sm font-medium">Caller Info</p>
              <p className="text-xs text-muted-foreground">Name, email, phone if mentioned</p>
            </div>
            <Switch
              checked={settings.defaults?.callerInfo ?? true}
              onCheckedChange={(v) => onChange({ defaults: { ...settings.defaults, callerInfo: v } })}
              disabled={readOnly || !settings.enabled}
            />
          </div>
        </div>
      </div>

      <Separator />

      {/* Template Categories */}
      <div className="space-y-3">
        <Label>Template Categories</Label>
        <p className="text-xs text-muted-foreground">
          Enable common extraction fields based on use case.
        </p>

        {Object.keys(templates).length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {Object.entries(templates).map(([key, category]) => {
              const isEnabled = enabledCategories.includes(key);
              return (
                <button
                  key={key}
                  type="button"
                  disabled={readOnly || !settings.enabled}
                  onClick={() => toggleCategory(key)}
                  className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors ${isEnabled
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-background text-muted-foreground hover:bg-muted"
                    } ${(readOnly || !settings.enabled) ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  <span>{getCategoryIcon(category.icon)}</span>
                  <span>{category.label}</span>
                </button>
              );
            })}
          </div>
        ) : (
          <div className="text-xs text-muted-foreground italic">Loading templates...</div>
        )}

        {/* Enabled Category Fields */}
        {enabledCategories.length > 0 && settings.enabled && (
          <div className="mt-4 space-y-4 rounded-lg border p-4 bg-muted/20">
            {enabledCategories.map((catKey) => {
              const category = templates[catKey];
              if (!category) return null;

              return (
                <div key={catKey} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{getCategoryIcon(category.icon)} {category.label}</span>
                    <Badge variant="secondary" className="text-[10px]">Enabled</Badge>
                  </div>
                  <div className="space-y-1">
                    {category.fields.map((field) => {
                      const isDisabled = disabledFields.includes(field.name);
                      return (
                        <div key={field.name} className="flex items-center gap-3 rounded bg-background p-2 border">
                          <Switch
                            checked={!isDisabled}
                            onCheckedChange={() => toggleField(field.name)}
                            disabled={readOnly}
                            className="scale-75"
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-mono">{field.name}</span>
                              <Badge variant="outline" className="text-[10px]">{field.type}</Badge>
                              {isDisabled && <span className="text-xs text-muted-foreground italic">← disabled by user</span>}
                            </div>
                            <p className="text-xs text-muted-foreground truncate">{field.description}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      <Separator />

      {/* AI Field Suggestions */}
      {!readOnly && settings.enabled && agentPrompt?.trim() && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>AI-Suggested Fields</Label>
              <p className="text-xs text-muted-foreground">
                Generate extraction fields based on your agent&apos;s prompt.
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="gap-1.5"
              disabled={isGenerating}
              onClick={generateFieldSuggestions}
            >
              {isGenerating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              {isGenerating ? "Generating..." : "Generate Fields"}
            </Button>
          </div>

          {showSuggestions && (
            <div className="rounded-lg border bg-muted/20 p-3 space-y-2">
              {isGenerating ? (
                <div className="flex items-center justify-center py-4 text-sm text-muted-foreground">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing your agent&apos;s prompt...
                </div>
              ) : suggestedFields.length > 0 ? (
                <>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-muted-foreground">
                      {suggestedFields.length} field{suggestedFields.length !== 1 ? "s" : ""} suggested
                    </span>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 gap-1 text-xs"
                      onClick={addAllSuggestedFields}
                    >
                      <Plus className="h-3 w-3" />
                      Add All
                    </Button>
                  </div>
                  {suggestedFields.map((field) => (
                    <div key={field.name} className="flex items-center gap-2 rounded border bg-background p-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-mono">{field.name}</span>
                          <Badge variant="outline" className="text-[10px]">{field.type}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground truncate">{field.description}</p>
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1 shrink-0"
                        onClick={() => addSuggestedField(field)}
                      >
                        <Plus className="h-3 w-3" />
                        Add
                      </Button>
                    </div>
                  ))}
                </>
              ) : (
                <div className="flex items-center justify-center py-3 text-xs text-muted-foreground">
                  No additional fields suggested. Your current setup looks complete!
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <Separator />

      {/* Custom Fields */}
      <div className="space-y-3">
        <Label>Custom Fields</Label>
        {(settings.customFields || []).length > 0 && (
          <ScrollArea className="max-h-[200px]">
            <div className="space-y-2">
              {settings.customFields.map((field, idx) => (
                <div key={idx} className="flex items-center gap-2 rounded border p-2">
                  <div className="flex-1">
                    <span className="text-sm font-mono font-medium">{field.name}</span>
                    <Badge variant="outline" className="ml-2 text-[10px]">
                      {field.type}
                    </Badge>
                    <p className="text-xs text-muted-foreground">{field.description}</p>
                  </div>
                  {!readOnly && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() =>
                        onChange({
                          customFields: settings.customFields.filter((_, i) => i !== idx),
                        })
                      }
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </ScrollArea>
        )}
        {!readOnly && settings.enabled && (
          <div className="space-y-2 rounded-lg border p-3">
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">Field Name</Label>
                <Input
                  value={fieldName}
                  onChange={(e) => setFieldName(e.target.value)}
                  placeholder="e.g., appointment_booked"
                  className="h-8"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Type</Label>
                <Select
                  value={fieldType}
                  onValueChange={(v) => setFieldType(v as ExtractionField["type"])}
                >
                  <SelectTrigger className="h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="string">String</SelectItem>
                    <SelectItem value="boolean">Boolean</SelectItem>
                    <SelectItem value="number">Number</SelectItem>
                    <SelectItem value="integer">Integer</SelectItem>
                    <SelectItem value="array">Array</SelectItem>
                    <SelectItem value="object">Object</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Description</Label>
              <Textarea
                value={fieldDesc}
                onChange={(e) => setFieldDesc(e.target.value)}
                placeholder="What should the AI extract?"
                className="h-16 resize-none"
              />
            </div>
            <Button variant="outline" size="sm" className="gap-1" onClick={addField}>
              <Plus className="h-3.5 w-3.5" />
              Add Field
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Webhook Settings Tab ────────────────────────────────────

function WebhookSettingsTab({
  settings,
  onChange,
  readOnly,
}: {
  settings: WebhookSettings;
  onChange: (patch: Partial<WebhookSettings>) => void;
  readOnly: boolean;
}) {
  const toggleEvent = (event: string) => {
    const events = settings.events.includes(event)
      ? settings.events.filter((e) => e !== event)
      : [...settings.events, event];
    onChange({ events });
  };

  return (
    <div className="space-y-5">
      {/* Enable Toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable Webhooks</Label>
          <p className="text-xs text-muted-foreground">
            Send events to the configured URL.
          </p>
        </div>
        <Switch
          checked={settings.enabled}
          onCheckedChange={(v) => onChange({ enabled: v })}
          disabled={readOnly}
        />
      </div>

      {/* URL */}
      <div className="space-y-2">
        <Label htmlFor="webhook-url">Webhook URL</Label>
        <Input
          id="webhook-url"
          type="url"
          value={settings.url}
          onChange={(e) => onChange({ url: e.target.value })}
          placeholder="https://api.example.com/webhooks/SphereVoice"
          readOnly={readOnly}
          disabled={!settings.enabled}
        />
      </div>

      {/* Events */}
      <div className="space-y-3">
        <Label>Events</Label>
        <div className="grid grid-cols-2 gap-2">
          {WEBHOOK_EVENTS.map((evt) => (
            <div
              key={evt.value}
              className="flex items-center gap-2 rounded-lg border p-2"
            >
              <Switch
                checked={settings.events.includes(evt.value)}
                onCheckedChange={() => toggleEvent(evt.value)}
                disabled={readOnly || !settings.enabled}
                className="scale-75"
              />
              <span className="text-xs">{evt.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Timeout */}
      <div className="space-y-2">
        <Label htmlFor="webhook-timeout">Timeout (ms)</Label>
        <Input
          id="webhook-timeout"
          type="number"
          value={settings.timeoutMs}
          onChange={(e) => onChange({ timeoutMs: parseInt(e.target.value, 10) || 5000 })}
          min={1000}
          max={30000}
          readOnly={readOnly}
          disabled={!settings.enabled}
        />
      </div>

      {/* Retry Count */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>Retry Count</Label>
          <span className="text-sm font-medium">{settings.retryCount}</span>
        </div>
        <Slider
          value={[settings.retryCount]}
          onValueChange={([v]) => onChange({ retryCount: v })}
          min={0}
          max={10}
          step={1}
          disabled={readOnly || !settings.enabled}
        />
        <p className="text-xs text-muted-foreground">
          Number of delivery retries on failure (exponential backoff).
        </p>
      </div>
    </div>
  );
}

// ── CRM Writeback Tab ──────────────────────────────────────

const CRM_MODULES = [
  { value: "Contacts", label: "Contacts" },
  { value: "Leads", label: "Leads" },
  { value: "Deals", label: "Deals" },
];

function CrmWritebackTab({
  settings,
  onChange,
  readOnly = false,
  agentId,
  tenantId,
}: {
  settings: CrmWritebackSettings;
  onChange: (patch: Partial<CrmWritebackSettings>) => void;
  readOnly?: boolean;
  agentId?: string;
  tenantId?: string;
}) {
  const [newExtracted, setNewExtracted] = useState("");
  const [newCrmField, setNewCrmField] = useState("");

  const { data: promptData, isLoading: varsLoading } = useAgentPromptVariables(
    agentId ?? ""
  );
  const { data: fieldsData, isLoading: fieldsLoading } = useCrmModuleFields(
    settings.crmModule,
    tenantId
  );

  const extractionFields = (promptData?.extraction_fields ?? [])
    .map((f) => (f as { name?: string; description?: string }).name || "")
    .filter(Boolean);
  const writableCrmFields = (fieldsData?.fields ?? []).filter(
    (f) => !f.read_only
  );
  const entries = Object.entries(settings.mapping);
  const mappedExtractions = new Set(entries.map(([k]) => k));
  const unmappedExtractions = extractionFields.filter(
    (f) => !mappedExtractions.has(f)
  );

  function addMapping() {
    if (!newExtracted || !newCrmField) return;
    onChange({
      mapping: {
        ...settings.mapping,
        [newExtracted]: newCrmField,
      },
    });
    setNewExtracted("");
    setNewCrmField("");
  }

  function removeMapping(key: string) {
    const updated = { ...settings.mapping };
    delete updated[key];
    onChange({ mapping: updated });
  }

  function autoMap() {
    const newMappings: Record<string, string> = { ...settings.mapping };
    for (const fieldName of extractionFields) {
      if (newMappings[fieldName]) continue;
      const match = writableCrmFields.find(
        (f) =>
          f.api_name.toLowerCase() === fieldName.toLowerCase() ||
          f.display_label.toLowerCase().replace(/\s+/g, "_") ===
          fieldName.toLowerCase()
      );
      if (match) {
        newMappings[fieldName] = match.api_name;
      }
    }
    onChange({ mapping: newMappings });
  }

  const isLoading = varsLoading || fieldsLoading;

  return (
    <div className="space-y-5">
      {/* Master toggle */}
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label>Enable CRM Writeback</Label>
          <p className="text-xs text-muted-foreground">
            Automatically push extracted data to your CRM after each call.
          </p>
        </div>
        <Switch
          checked={settings.enabled}
          onCheckedChange={(v) => onChange({ enabled: v })}
          disabled={readOnly}
        />
      </div>

      {settings.enabled && (
        <>
          {/* Target Module */}
          <div className="space-y-2">
            <Label>Target CRM Module</Label>
            <Select
              value={settings.crmModule}
              onValueChange={(v) => onChange({ crmModule: v })}
              disabled={readOnly}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select CRM module" />
              </SelectTrigger>
              <SelectContent>
                {CRM_MODULES.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {isLoading && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground py-4">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading extraction fields and CRM fields…
            </div>
          )}

          {/* Unmapped fields info */}
          {unmappedExtractions.length > 0 && !isLoading && (
            <div className="rounded-lg border border-blue-200 bg-blue-50 dark:bg-blue-950/20 dark:border-blue-800 p-3 space-y-2">
              <p className="text-xs font-medium text-blue-800 dark:text-blue-300">
                {unmappedExtractions.length} extraction field
                {unmappedExtractions.length > 1 ? "s" : ""} not mapped to CRM:
              </p>
              <div className="flex flex-wrap gap-1.5">
                {unmappedExtractions.map((f) => (
                  <Badge
                    key={f}
                    variant="outline"
                    className="text-xs font-mono border-blue-300 dark:border-blue-700"
                  >
                    {f}
                  </Badge>
                ))}
              </div>
              {writableCrmFields.length > 0 && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={autoMap}
                  disabled={readOnly}
                  className="mt-1"
                >
                  Auto-Map Matching Fields
                </Button>
              )}
            </div>
          )}

          {/* Existing mappings */}
          {entries.length > 0 && (
            <div className="space-y-2">
              <Label className="text-xs text-muted-foreground">
                Current Mappings
              </Label>
              {entries.map(([extracted, crmField]) => (
                <div
                  key={extracted}
                  className="flex items-center gap-2 rounded-md border px-3 py-2"
                >
                  <Badge
                    variant="secondary"
                    className="text-xs font-mono shrink-0"
                  >
                    {extracted}
                  </Badge>
                  <ArrowRight className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="flex-1 text-sm">{crmField}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => removeMapping(extracted)}
                    disabled={readOnly}
                    className="h-7 w-7 text-destructive"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              ))}
            </div>
          )}

          {/* Add new mapping */}
          {!isLoading &&
            extractionFields.length > 0 &&
            settings.crmModule && (
              <div className="space-y-3 rounded-lg border p-4">
                <p className="text-xs font-medium text-muted-foreground">
                  Add Mapping
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Extracted Field</Label>
                    <Select
                      value={newExtracted}
                      onValueChange={setNewExtracted}
                      disabled={readOnly}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select extracted field" />
                      </SelectTrigger>
                      <SelectContent>
                        {extractionFields.map((f) => (
                          <SelectItem
                            key={f}
                            value={f}
                            disabled={mappedExtractions.has(f)}
                          >
                            {f}
                            {mappedExtractions.has(f) ? " (mapped)" : ""}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>CRM Field</Label>
                    <Select
                      value={newCrmField}
                      onValueChange={setNewCrmField}
                      disabled={readOnly}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select CRM field" />
                      </SelectTrigger>
                      <SelectContent>
                        {writableCrmFields.map((f) => (
                          <SelectItem key={f.api_name} value={f.api_name}>
                            {f.display_label} ({f.api_name})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={addMapping}
                  disabled={readOnly || !newExtracted || !newCrmField}
                >
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Add Mapping
                </Button>
              </div>
            )}

          {/* No extraction fields */}
          {!isLoading && extractionFields.length === 0 && (
            <div className="rounded-lg border border-dashed p-4 text-center">
              <p className="text-sm text-muted-foreground">
                No extraction fields defined on this agent.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Configure extraction fields in the Post-Call Extraction section
                above to enable CRM writeback mapping.
              </p>
            </div>
          )}

          {/* No CRM module selected */}
          {!isLoading && settings.crmModule === "" && (
            <p className="text-sm text-muted-foreground">
              Select a target CRM module above to configure field mappings.
            </p>
          )}
        </>
      )}
    </div>
  );
}
