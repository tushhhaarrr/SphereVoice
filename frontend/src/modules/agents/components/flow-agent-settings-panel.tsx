"use client";

import { Brain, Mic, Phone, Volume2, Webhook } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { AgentProviderBindings, AgentSettings, DenoisingMode } from "./agent-settings";

const LANGUAGES = [
  { value: "en", label: "English" },
  { value: "es", label: "Spanish" },
  { value: "hi", label: "Hindi" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
];

const TTS_PROVIDERS = [
  { value: "cartesia", label: "Cartesia (Sonic-3)" },
  { value: "elevenlabs", label: "ElevenLabs" },
  { value: "openai", label: "OpenAI TTS" },
  { value: "azure", label: "Azure Speech" },
];

const LLM_MODELS = [
  { value: "groq/meta-llama/llama-4-scout-17b-16e-instruct", label: "Groq — Llama 4 Scout 17B" },
  { value: "groq/openai/gpt-oss-120b", label: "Groq — GPT-OSS 120B" },
  { value: "groq/llama-3.3-70b-versatile", label: "Groq — Llama 3.3 70B" },
  { value: "groq/llama-3.1-8b-instant", label: "Groq — Llama 3.1 8B" },
  { value: "openai/gpt-4o", label: "OpenAI — GPT-4o" },
  { value: "openai/gpt-4o-mini", label: "OpenAI — GPT-4o Mini" },
  { value: "anthropic/claude-sonnet-4-20250514", label: "Anthropic — Claude Sonnet 4" },
];

const VOICEMAIL_OPTIONS = [
  { value: "hang_up", label: "Hang Up" },
  { value: "leave_message", label: "Leave Message" },
  { value: "disabled", label: "Disabled" },
];

function SettingsSection({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border bg-background p-4 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-muted text-foreground">
          <Icon className="h-4 w-4" />
        </div>
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>
        </div>
      </div>
      <div className="mt-4 space-y-4">{children}</div>
    </section>
  );
}

interface FlowAgentSettingsPanelProps {
  settings: AgentSettings;
  onChange: (settings: AgentSettings) => void;
  providerBindings?: AgentProviderBindings;
}

export function FlowAgentSettingsPanel({ settings, onChange, providerBindings }: FlowAgentSettingsPanelProps) {
  const update = <K extends keyof AgentSettings>(section: K, patch: Partial<AgentSettings[K]>) => {
    onChange({
      ...settings,
      [section]: { ...settings[section], ...patch },
    });
  };

  const sttProviders = providerBindings?.sttProviders ?? [];
  const sttModels = providerBindings?.sttModels ?? [];
  const llmProviders = providerBindings?.llmProviders ?? [];
  const ttsProviders = providerBindings?.ttsProviders.length ? providerBindings.ttsProviders : TTS_PROVIDERS;
  const ttsModels = providerBindings?.ttsModels ?? [];
  const voiceOptions = providerBindings?.ttsVoices ?? [];
  const llmModels = providerBindings?.llmModels.length ? providerBindings.llmModels : LLM_MODELS;

  return (
    <div className="space-y-4">
      <SettingsSection
        icon={Volume2}
        title="TTS"
        description="Choose the provider, model, voice, and language for spoken responses."
      >
        <div className="space-y-2">
          <Label>Language</Label>
          <Select value={settings.voiceLanguage.language} onValueChange={(value) => update("voiceLanguage", { language: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LANGUAGES.map((language) => (
                <SelectItem key={language.value} value={language.value}>{language.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>TTS Provider</Label>
          <Select value={settings.voiceLanguage.ttsProvider || undefined} onValueChange={(value) => update("voiceLanguage", { ttsProvider: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ttsProviders.map((provider) => (
                <SelectItem key={provider.value} value={provider.value}>{provider.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>TTS Model</Label>
          {ttsModels.length > 0 ? (
            <Select value={settings.voiceLanguage.ttsModel || undefined} onValueChange={(value) => update("voiceLanguage", { ttsModel: value })}>
              <SelectTrigger>
                <SelectValue placeholder="Select a synced TTS model" />
              </SelectTrigger>
              <SelectContent>
                {ttsModels.map((model) => (
                  <SelectItem key={model.value} value={model.value}>{model.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              value={settings.voiceLanguage.ttsModel}
              onChange={(event) => update("voiceLanguage", { ttsModel: event.target.value })}
              placeholder="Enter TTS model from provider"
            />
          )}
        </div>
        <div className="space-y-2">
          <Label>Voice ID</Label>
          {voiceOptions.length > 0 ? (
            <Select value={settings.voiceLanguage.voiceId || undefined} onValueChange={(value) => update("voiceLanguage", { voiceId: value })}>
              <SelectTrigger>
                <SelectValue placeholder="Select a synced voice" />
              </SelectTrigger>
              <SelectContent>
                {voiceOptions.map((voice) => (
                  <SelectItem key={voice.value} value={voice.value}>{voice.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              value={settings.voiceLanguage.voiceId}
              onChange={(event) => update("voiceLanguage", { voiceId: event.target.value })}
              placeholder="Enter voice ID from provider"
            />
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <Label>Voice Speed</Label>
            <span>{settings.voiceLanguage.voiceSpeed.toFixed(1)}x</span>
          </div>
          <Slider value={[settings.voiceLanguage.voiceSpeed]} onValueChange={([value]) => update("voiceLanguage", { voiceSpeed: value })} min={0.5} max={2} step={0.1} />
        </div>
      </SettingsSection>

      <SettingsSection
        icon={Brain}
        title="LLM"
        description="Choose the provider and model that powers the agent's reasoning."
      >
        <div className="space-y-2">
          <Label>LLM Provider</Label>
          <Select value={settings.llm.provider || undefined} onValueChange={(value) => update("llm", { provider: value })}>
            <SelectTrigger>
              <SelectValue placeholder="Select LLM provider" />
            </SelectTrigger>
            <SelectContent>
              {llmProviders.map((provider) => (
                <SelectItem key={provider.value} value={provider.value}>{provider.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>LLM Model</Label>
          <Select value={settings.llm.model || undefined} onValueChange={(value) => update("llm", { model: value })}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {llmModels.map((model) => (
                <SelectItem key={model.value} value={model.value}>{model.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <Label>Temperature</Label>
            <span>{settings.llm.temperature.toFixed(1)}</span>
          </div>
          <Slider value={[settings.llm.temperature]} onValueChange={([value]) => update("llm", { temperature: value })} min={0} max={1.5} step={0.1} />
        </div>
        <div className="space-y-2">
          <Label>Max Tokens</Label>
          <Input type="number" value={settings.llm.maxTokens} onChange={(event) => update("llm", { maxTokens: Number(event.target.value) || 0 })} />
        </div>
        <div className="flex items-center justify-between rounded-lg border px-3 py-3">
          <div>
            <Label>Structured Output</Label>
            <p className="mt-1 text-xs text-muted-foreground">Prefer schema-safe outputs for extraction-heavy flows.</p>
          </div>
          <Switch checked={settings.llm.structuredOutput} onCheckedChange={(checked) => update("llm", { structuredOutput: checked })} />
        </div>
      </SettingsSection>

      <SettingsSection
        icon={Phone}
        title="Call Behavior"
        description="Define silence, voicemail, and long-call handling for the flow."
      >
        <div className="space-y-2">
          <Label>Voicemail Handling</Label>
          <Select
            value={settings.callBehavior.voicemailDetection}
            onValueChange={(value) => update("callBehavior", { voicemailDetection: value as AgentSettings["callBehavior"]["voicemailDetection"] })}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {VOICEMAIL_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Silence Timeout (s)</Label>
            <Input type="number" min={5} max={1800} value={settings.callBehavior.endOnSilenceSeconds} onChange={(event) => update("callBehavior", { endOnSilenceSeconds: Math.max(5, Math.min(1800, Number(event.target.value) || 8)) })} />
            <p className="text-xs text-muted-foreground">5s – 30m</p>
          </div>
          <div className="space-y-2">
            <Label>Max Call Duration (min)</Label>
            <Input type="number" min={1} max={120} value={settings.callBehavior.maxCallDurationMinutes} onChange={(event) => update("callBehavior", { maxCallDurationMinutes: Math.max(1, Math.min(120, Number(event.target.value) || 4)) })} />
            <p className="text-xs text-muted-foreground">1 min – 2 hours</p>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label>Ring Duration (s)</Label>
            <Input type="number" min={5} max={300} value={settings.callBehavior.ringDurationSeconds} onChange={(event) => update("callBehavior", { ringDurationSeconds: Math.max(5, Math.min(300, Number(event.target.value) || 30)) })} />
            <p className="text-xs text-muted-foreground">5s – 300s. Max ring time for outbound/transfer calls.</p>
          </div>
        </div>
        <div className="flex items-center justify-between rounded-lg border px-3 py-3">
          <div>
            <Label>IVR Detection</Label>
            <p className="mt-1 text-xs text-muted-foreground">Detect IVR systems before starting the conversation.</p>
          </div>
          <Switch checked={settings.callBehavior.ivrDetection} onCheckedChange={(checked) => update("callBehavior", { ivrDetection: checked })} />
        </div>
      </SettingsSection>

      <SettingsSection
        icon={Mic}
        title="STT & Audio"
        description="Choose the speech-to-text provider and tune live listening behavior."
      >
        <div className="space-y-2">
          <Label>STT Provider</Label>
          <Select value={settings.transcription.sttProvider || undefined} onValueChange={(value) => update("transcription", { sttProvider: value })}>
            <SelectTrigger>
              <SelectValue placeholder="Select STT provider" />
            </SelectTrigger>
            <SelectContent>
              {sttProviders.map((provider) => (
                <SelectItem key={provider.value} value={provider.value}>{provider.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>STT Model</Label>
          {sttModels.length > 0 ? (
            <Select value={settings.transcription.sttModel || undefined} onValueChange={(value) => update("transcription", { sttModel: value })}>
              <SelectTrigger>
                <SelectValue placeholder="Select STT model" />
              </SelectTrigger>
              <SelectContent>
                {sttModels.map((model) => (
                  <SelectItem key={model.value} value={model.value}>{model.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <Input
              value={settings.transcription.sttModel}
              onChange={(event) => update("transcription", { sttModel: event.target.value })}
              placeholder="Enter STT model from provider"
            />
          )}
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <Label>Responsiveness</Label>
            <span>{Math.round(settings.speech.responsiveness * 100)}%</span>
          </div>
          <Slider value={[settings.speech.responsiveness]} onValueChange={([value]) => update("speech", { responsiveness: value })} min={0} max={1} step={0.05} />
        </div>
        {settings.transcription.sttProvider === "groq_whisper" && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200">
            Live browser and phone calls currently fall back to a realtime STT provider instead of Groq Whisper because the current Groq STT path is not true streaming STT.
          </div>
        )}
        <div className="flex items-center justify-between rounded-lg border px-3 py-3">
          <div>
            <Label>Denoising</Label>
            <p className="mt-1 text-xs text-muted-foreground">Reduce background noise before transcription.</p>
          </div>
          <Select value={settings.transcription.denoisingMode ?? "noise_only"} onValueChange={(v) => update("transcription", { denoisingMode: v as DenoisingMode })}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="noise_only">Remove noise</SelectItem>
              <SelectItem value="noise_and_speech">Remove noise + background speech</SelectItem>
              <SelectItem value="no_denoising">No denoising</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <Label>Boosted Keywords</Label>
          <Textarea
            value={settings.transcription.boostedKeywords.join(", ")}
            onChange={(event) => update("transcription", {
              boostedKeywords: event.target.value.split(",").map((entry) => entry.trim()).filter(Boolean),
            })}
            rows={3}
            placeholder="insurance, claims, member ID"
          />
        </div>
      </SettingsSection>

      <SettingsSection
        icon={Webhook}
        title="Webhooks"
        description="Send lifecycle events from this flow to your backend."
      >
        <div className="flex items-center justify-between rounded-lg border px-3 py-3">
          <div>
            <Label>Enable Webhooks</Label>
            <p className="mt-1 text-xs text-muted-foreground">Send events like call started and call ended to your endpoint.</p>
          </div>
          <Switch checked={settings.webhooks.enabled} onCheckedChange={(checked) => update("webhooks", { enabled: checked })} />
        </div>
        <div className="space-y-2">
          <Label>Webhook URL</Label>
          <Input
            value={settings.webhooks.url}
            onChange={(event) => update("webhooks", { url: event.target.value })}
            placeholder="https://api.example.com/voice-events"
          />
        </div>
      </SettingsSection>
    </div>
  );
}