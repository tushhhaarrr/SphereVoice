import type { Provider, ProviderCategory } from "../types";

export type ProviderCatalogItem = {
    id: string;
    name: string;
    description?: string;
    owner?: string;
    language?: string;
    locale?: string;
    locale_name?: string;
    local_name?: string;
    gender?: string;
    voice_type?: string;
    sample_rate_hertz?: string;
    status?: string;
    words_per_minute?: number;
    styles?: string[];
    tags?: string[];
    roles?: string[];
    secondary_locales?: string[];
    context_window?: number;
    is_default?: boolean;
};

export type ProviderCatalog = {
    source?: string;
    refreshed_at?: string | null;
    models: ProviderCatalogItem[];
    voices: ProviderCatalogItem[];
};

export const CATEGORY_LABELS: Record<ProviderCategory, string> = {
    stt: "Speech to Text",
    llm: "Language Model",
    tts: "Text to Speech",
    telephony: "Telephony",
};

export const CATEGORY_COLORS: Record<ProviderCategory, string> = {
    stt: "bg-sky-100 text-sky-700",
    llm: "bg-emerald-100 text-emerald-700",
    tts: "bg-amber-100 text-amber-700",
    telephony: "bg-violet-100 text-violet-700",
};

export const PROVIDER_OPTIONS: Record<ProviderCategory, string[]> = {
    stt: ["soniox", "deepgram", "groq_whisper", "assemblyai", "azure_speech"],
    llm: ["openai", "groq", "anthropic", "cerebras", "azure_openai"],
    tts: ["cartesia", "elevenlabs", "groq_tts", "inworld", "openai_tts", "lmnt", "azure_speech", "sarvam", "smallest"],
    telephony: ["plivo", "twilio", "vobiz", "vonage", "telnyx"],
};

export const PROVIDER_FAMILY_OPTIONS: Record<ProviderCategory, string[]> = {
    stt: ["soniox", "deepgram", "groq", "assemblyai", "azure"],
    llm: ["openai", "groq", "anthropic", "cerebras", "azure"],
    tts: ["cartesia", "elevenlabs", "groq", "inworld", "openai", "lmnt", "azure", "sarvam", "smallest"],
    telephony: ["plivo", "twilio", "vobiz", "vonage", "telnyx"],
};

export const RECOMMENDED_DEFAULTS: Record<ProviderCategory, string> = {
    stt: "soniox",
    llm: "openai",
    tts: "cartesia",
    telephony: "plivo",
};

const PROVIDER_LABELS: Record<string, string> = {
    soniox: "Soniox",
    azure: "Azure",
    deepgram: "Deepgram",
    deepgram_flux: "Deepgram Flux",
    groq: "Groq",
    groq_whisper: "Groq Whisper",
    groq_tts: "Groq TTS",
    assemblyai: "AssemblyAI",
    azure_openai: "Azure OpenAI",
    azure_speech: "Azure Speech",
    openai: "OpenAI",
    openai_tts: "OpenAI TTS",
    openai_whisper: "OpenAI Whisper",
    anthropic: "Anthropic",
    cerebras: "Cerebras",
    cartesia: "Cartesia",
    elevenlabs: "ElevenLabs",
    inworld: "Inworld",
    lmnt: "LMNT",
    sarvam: "Sarvam",
    smallest: "Smallest AI",
    twilio: "Twilio",
    vobiz: "Vobiz",
    plivo: "Plivo",
    vonage: "Vonage",
    telnyx: "Telnyx",
    playht: "PlayHT",
};

const PROVIDER_DESCRIPTIONS: Record<string, string> = {
    soniox: "Realtime multilingual STT with automatic language identification and optional speaker diarization.",
    azure: "Azure-hosted LLM and speech providers grouped as one family.",
    deepgram: "Streaming speech-to-text with low-latency transcription.",
    deepgram_flux: "Deepgram Flux endpointing optimized for fast turn detection.",
    groq: "Hosted LLM inference optimized for low latency.",
    groq_whisper: "Groq-hosted Whisper speech-to-text.",
    groq_tts: "Groq-hosted text-to-speech voices.",
    assemblyai: "Speech-to-text provider focused on transcription APIs.",
    azure_openai: "Azure-hosted OpenAI deployment.",
    azure_speech: "Azure Speech for STT or TTS workloads.",
    openai: "OpenAI chat and reasoning models.",
    openai_tts: "OpenAI text-to-speech voices.",
    openai_whisper: "OpenAI Whisper speech-to-text.",
    anthropic: "Claude-family models for instruction-heavy tasks.",
    cerebras: "Cerebras inference platform for fast LLM responses.",
    cartesia: "Low-latency Sonic voices with strong streaming support.",
    elevenlabs: "High-quality TTS voices and voice cloning.",
    inworld: "Inworld voice and character services.",
    lmnt: "Real-time TTS voices optimized for conversational use.",
    sarvam: "Indian-language TTS with structured voice metadata and multilingual coverage.",
    smallest: "Low-latency Lightning TTS voices from Smallest AI.",
    twilio: "Telephony routing, phone numbers, and call execution.",
    vobiz: "Vobiz telephony provider for voice calling and phone numbers (Plivo-powered).",
    plivo: "Plivo — primary telephony provider with sub-account support for multi-tenant phone number management.",
    vonage: "Telephony provider for voice and messaging.",
    telnyx: "Telephony provider for SIP and phone numbers.",
    playht: "Broad text-to-speech voice catalog.",
};

function titleCase(value: string): string {
    return value
        .split(/[_\-\s]+/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

export function getProviderFamilyId(providerName: string): string {
    if (providerName.startsWith("groq")) {
        return "groq";
    }

    if (providerName.startsWith("openai")) {
        return "openai";
    }

    if (providerName === "azure_openai" || providerName === "azure_speech") {
        return "azure";
    }

    if (providerName.startsWith("deepgram")) {
        return "deepgram";
    }

    return providerName;
}

export function normalizeProviderName(providerName: string, category: ProviderCategory): string {
    const family = getProviderFamilyId(providerName);
    if (category === "stt") {
        if (family === "groq") return "groq_whisper";
        if (family === "openai") return "openai_whisper";
        if (family === "azure") return "azure_speech";
    }

    if (category === "llm") {
        if (family === "azure") return "azure_openai";
        return family;
    }

    if (category === "tts") {
        if (family === "groq") return "groq_tts";
        if (family === "openai") return "openai_tts";
        if (family === "azure") return "azure_speech";
    }

    return providerName;
}

function asObject(value: unknown): Record<string, unknown> {
    return value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : {};
}

function asStringArray(value: unknown): string[] | undefined {
    if (!Array.isArray(value)) {
        return undefined;
    }

    const items = value.filter((item): item is string => typeof item === "string" && item.length > 0);
    return items.length > 0 ? items : undefined;
}

function asCatalogItems(value: unknown): ProviderCatalogItem[] {
    if (!Array.isArray(value)) {
        return [];
    }

    const items: Array<ProviderCatalogItem | null> = value.map((item) => {
        const record = asObject(item);
        const id = typeof record.id === "string" ? record.id : "";
        if (!id) {
            return null;
        }

        return {
            id,
            name: typeof record.name === "string" && record.name ? record.name : id,
            description: typeof record.description === "string" ? record.description : undefined,
            owner: typeof record.owner === "string" ? record.owner : undefined,
            language: typeof record.language === "string" ? record.language : undefined,
            locale: typeof record.locale === "string" ? record.locale : undefined,
            locale_name: typeof record.locale_name === "string" ? record.locale_name : undefined,
            local_name: typeof record.local_name === "string" ? record.local_name : undefined,
            gender: typeof record.gender === "string" ? record.gender : undefined,
            voice_type: typeof record.voice_type === "string" ? record.voice_type : undefined,
            sample_rate_hertz:
                typeof record.sample_rate_hertz === "string" ? record.sample_rate_hertz : undefined,
            status: typeof record.status === "string" ? record.status : undefined,
            words_per_minute:
                typeof record.words_per_minute === "number" ? record.words_per_minute : undefined,
            styles: asStringArray(record.styles),
            tags: asStringArray(record.tags),
            roles: asStringArray(record.roles),
            secondary_locales: asStringArray(record.secondary_locales),
            context_window:
                typeof record.context_window === "number" ? record.context_window : undefined,
            is_default: record.is_default === true,
        } satisfies ProviderCatalogItem;
    });

    return items.filter((item): item is ProviderCatalogItem => item !== null);
}

export function parseProviderCatalog(config: Record<string, unknown> | null | undefined): ProviderCatalog {
    const catalog = asObject(asObject(config).catalog);

    return {
        source: typeof catalog.source === "string" ? catalog.source : undefined,
        refreshed_at: typeof catalog.refreshed_at === "string" ? catalog.refreshed_at : null,
        models: asCatalogItems(catalog.models),
        voices: asCatalogItems(catalog.voices),
    };
}

export function getProviderLabel(providerName: string): string {
    return PROVIDER_LABELS[providerName] ?? titleCase(providerName);
}

export function getProviderDescription(providerName: string): string {
    return PROVIDER_DESCRIPTIONS[providerName] ?? "Custom provider configuration.";
}

export function getCategoryProviders(
    providers: Provider[],
    category: ProviderCategory,
): Provider[] {
    return providers.filter((provider) => provider.provider_category === category && provider.is_active);
}

export function getDefaultProviderForCategory(
    providers: Provider[],
    category: ProviderCategory,
): Provider | undefined {
    const categoryProviders = getCategoryProviders(providers, category);
    return (
        categoryProviders.find((provider) => provider.is_default) ??
        categoryProviders.find((provider) => provider.provider_name === RECOMMENDED_DEFAULTS[category]) ??
        categoryProviders[0]
    );
}

export function getProviderModels(provider: Provider): ProviderCatalogItem[] {
    return parseProviderCatalog(provider.config).models;
}

export function getProviderVoices(provider: Provider): ProviderCatalogItem[] {
    return parseProviderCatalog(provider.config).voices;
}

export function getProviderSelectedModel(provider: Provider): string | null {
    const config = asObject(provider.config);
    if (typeof config.model === "string" && config.model) {
        return config.model;
    }

    return getProviderModels(provider).find((item) => item.is_default)?.id ?? null;
}

export function getProviderSelectedVoice(provider: Provider): string | null {
    const config = asObject(provider.config);
    if (typeof config.voice_id === "string" && config.voice_id) {
        return config.voice_id;
    }

    return getProviderVoices(provider).find((item) => item.is_default)?.id ?? null;
}

export function getProviderScopeLabel(provider: Provider): string {
    if (provider.tenant_id) {
        return provider.is_default ? "Workspace default" : "Workspace";
    }
    return provider.is_default ? "Shared default" : "Shared";
}

export function getCatalogCountLabel(provider: Provider): string {
    const catalog = parseProviderCatalog(provider.config);
    const modelCount = catalog.models.length;
    const voiceCount = catalog.voices.length;

    if (modelCount === 0 && voiceCount === 0) {
        return "No synced catalog";
    }

    const parts: string[] = [];
    if (modelCount > 0) {
        parts.push(`${modelCount} model${modelCount === 1 ? "" : "s"}`);
    }
    if (voiceCount > 0) {
        parts.push(`${voiceCount} voice${voiceCount === 1 ? "" : "s"}`);
    }
    return parts.join(" • ");
}