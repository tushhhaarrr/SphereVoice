"use client";

/**
 * Provider workspace component.
 */

import { useMemo, useState, type ComponentType } from "react";
import {
    CheckCircle,
    Clock,
    FlaskConical,
    Layers3,
    Loader2,
    Plus,
    RefreshCcw,
    Save,
    ShieldCheck,
    Sparkles,
    Trash2,
    WandSparkles,
    XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { RoleGuard } from "@/modules/auth";
import {
    useDeleteProvider,
    useProvidersList,
    useRefreshProvider,
    useTestProvider,
    useUpdateProvider,
} from "../hooks/use-providers";
import {
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    RECOMMENDED_DEFAULTS,
    getCatalogCountLabel,
    getCategoryProviders,
    getDefaultProviderForCategory,
    getProviderDescription,
    getProviderFamilyId,
    getProviderLabel,
    getProviderModels,
    getProviderScopeLabel,
    getProviderSelectedModel,
    getProviderSelectedVoice,
    getProviderVoices,
    parseProviderCatalog,
    type ProviderCatalogItem,
} from "../lib/catalog";
import type { Provider, ProviderCategory } from "../types";
import { AddProviderDialog } from "./add-provider-dialog";

type ProviderFamilyMeta = {
    label: string;
    description: string;
    variants: Partial<Record<ProviderCategory, string>>;
};

type ProviderFamily = ProviderFamilyMeta & {
    id: string;
    configuredProviders: Partial<Record<ProviderCategory, Provider>>;
    connectedCount: number;
    configuredCount: number;
    defaultCount: number;
};

const DEFAULT_CATEGORIES: ProviderCategory[] = ["stt", "llm", "tts", "telephony"];

const PROVIDER_FAMILY_METADATA: Record<string, ProviderFamilyMeta> = {
    groq: {
        label: "Groq",
        description: "Manage Groq LLM, Whisper STT, and optional TTS from one place.",
        variants: {
            stt: "groq_whisper",
            llm: "groq",
            tts: "groq_tts",
        },
    },
    openai: {
        label: "OpenAI",
        description: "Keep OpenAI chat, Whisper, and TTS choices together.",
        variants: {
            stt: "openai_whisper",
            llm: "openai",
            tts: "openai_tts",
        },
    },
    azure: {
        label: "Azure",
        description: "Azure-hosted LLM and speech capabilities grouped in one family.",
        variants: {
            stt: "azure_speech",
            llm: "azure_openai",
            tts: "azure_speech",
        },
    },
    deepgram: {
        label: "Deepgram",
        description: "Streaming STT with Nova models.",
        variants: { stt: "deepgram" },
    },
    assemblyai: {
        label: "AssemblyAI",
        description: "Speech-to-text focused transcription provider.",
        variants: { stt: "assemblyai" },
    },
    anthropic: {
        label: "Anthropic",
        description: "Claude-family reasoning models.",
        variants: { llm: "anthropic" },
    },
    cerebras: {
        label: "Cerebras",
        description: "Fast hosted inference for LLM workloads.",
        variants: { llm: "cerebras" },
    },
    inworld: {
        label: "Inworld",
        description: "Recommended TTS default with structured models and voices.",
        variants: { tts: "inworld" },
    },
    cartesia: {
        label: "Cartesia",
        description: "Low-latency Sonic voices with fast startup.",
        variants: { tts: "cartesia" },
    },
    elevenlabs: {
        label: "ElevenLabs",
        description: "High-quality voices with live voice sync.",
        variants: { tts: "elevenlabs" },
    },
    lmnt: {
        label: "LMNT",
        description: "Real-time optimized TTS voices.",
        variants: { tts: "lmnt" },
    },
    sarvam: {
        label: "Sarvam",
        description: "Indian-language TTS provider with curated voice metadata.",
        variants: { tts: "sarvam" },
    },
    smallest: {
        label: "Smallest AI",
        description: "Lightning TTS voices with low-latency synthesis and synced voice catalogs.",
        variants: { tts: "smallest" },
    },
    playht: {
        label: "PlayHT",
        description: "Broad voice coverage for TTS use cases.",
        variants: { tts: "playht" },
    },
    twilio: {
        label: "Twilio",
        description: "Telephony routing, phone numbers, and call handling.",
        variants: { telephony: "twilio" },
    },
    plivo: {
        label: "Plivo",
        description: "Primary telephony provider with sub-account support.",
        variants: { telephony: "plivo" },
    },
    vonage: {
        label: "Vonage",
        description: "Telephony provider.",
        variants: { telephony: "vonage" },
    },
    telnyx: {
        label: "Telnyx",
        description: "Telephony provider.",
        variants: { telephony: "telnyx" },
    },
};

function buildProviderFamilies(providers: Provider[]): ProviderFamily[] {
    const families = new Map<string, ProviderFamily>();

    for (const provider of providers) {
        const familyId = provider.provider_family ?? getProviderFamilyId(provider.provider_name);
        const meta = PROVIDER_FAMILY_METADATA[familyId] ?? {
            label: getProviderLabel(provider.provider_name),
            description: getProviderDescription(provider.provider_name),
            variants: { [provider.provider_category]: provider.provider_name },
        };

        const existing = families.get(familyId) ?? {
            id: familyId,
            ...meta,
            configuredProviders: {},
            connectedCount: 0,
            configuredCount: 0,
            defaultCount: 0,
        };

        const currentForCategory = existing.configuredProviders[provider.provider_category];
        if (!currentForCategory || (!currentForCategory.is_default && provider.is_default)) {
            existing.configuredProviders[provider.provider_category] = provider;
        }

        families.set(familyId, existing);
    }

    return Array.from(families.values())
        .map((family) => {
            const configuredProviders = Object.values(family.configuredProviders);
            return {
                ...family,
                connectedCount: configuredProviders.filter((provider) => provider?.test_status === "success").length,
                configuredCount: configuredProviders.length,
                defaultCount: configuredProviders.filter((provider) => provider?.is_default).length,
            };
        })
        .sort((left, right) => {
            if (right.defaultCount !== left.defaultCount) {
                return right.defaultCount - left.defaultCount;
            }
            if (right.configuredCount !== left.configuredCount) {
                return right.configuredCount - left.configuredCount;
            }
            return left.label.localeCompare(right.label);
        });
}

function TestStatusBadge({ status }: { status: string | null }) {
    if (!status) return <span className="text-xs text-muted-foreground">Not tested</span>;

    switch (status) {
        case "success":
            return (
                <Badge variant="outline" className="gap-1 border-green-500 text-green-600">
                    <CheckCircle className="h-3 w-3" />
                    Connected
                </Badge>
            );
        case "failed":
            return (
                <Badge variant="outline" className="gap-1 border-red-500 text-red-600">
                    <XCircle className="h-3 w-3" />
                    Failed
                </Badge>
            );
        default:
            return (
                <Badge variant="outline" className="gap-1">
                    <Clock className="h-3 w-3" />
                    {status}
                </Badge>
            );
    }
}

interface ProviderListProps {
    tenantId?: string;
    tenantName?: string;
}

export function ProviderList({ tenantId, tenantName }: ProviderListProps = {}) {
    const [dialogOpen, setDialogOpen] = useState(false);

    const { data, isLoading, isFetching, error, refetch } = useProvidersList({ tenantId });

    const providers = useMemo(() => data?.providers ?? [], [data?.providers]);
    const families = useMemo(() => buildProviderFamilies(providers), [providers]);

    const stats = useMemo(() => {
        const connectedCount = providers.filter((provider) => provider.test_status === "success").length;
        const syncedCount = providers.filter(
            (provider) => getProviderModels(provider).length > 0 || getProviderVoices(provider).length > 0,
        ).length;

        return {
            families: families.length,
            records: providers.length,
            defaults: providers.filter((provider) => provider.is_default).length,
            connected: connectedCount,
            synced: syncedCount,
        };
    }, [families.length, providers]);

    if (isLoading) {
        return (
            <div className="flex items-center justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="rounded-md bg-destructive/10 px-4 py-3 text-sm text-destructive">
                Failed to load providers. Make sure the backend is running.
            </div>
        );
    }

    return (
        <div className="scroll-mt-40 space-y-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                    <h1 className="text-3xl font-semibold tracking-tight">Providers</h1>
                    <p className="max-w-3xl text-sm text-muted-foreground">
                        {tenantId
                            ? `Manage shared and workspace-owned provider capabilities for ${tenantName ?? "this workspace"}. Pick runtime defaults once, then manage each provider family in one place.`
                            : "Manage provider families instead of splitting the page by STT, LLM, or TTS. Set runtime defaults once, then manage each provider family below."}
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
                        {isFetching ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}
                        Reload
                    </Button>
                    <RoleGuard roles={["admin", "developer"]}>
                        <Button onClick={() => setDialogOpen(true)}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add Provider
                        </Button>
                    </RoleGuard>
                </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                <SummaryCard title="Families" value={String(stats.families)} description="Provider groups shown on this page" icon={Layers3} />
                <SummaryCard title="Records" value={String(stats.records)} description="Configured provider capability rows" icon={ShieldCheck} />
                <SummaryCard title="Defaults" value={String(stats.defaults)} description="Active runtime defaults across categories" icon={Sparkles} />
                <SummaryCard title="Connected" value={String(stats.connected)} description="Provider records that passed connection test" icon={CheckCircle} />
                <SummaryCard title="Catalog Ready" value={String(stats.synced)} description="Records with synced models or voices" icon={RefreshCcw} />
            </div>

            <section className="space-y-4">
                <div className="flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <h2 className="text-xl font-semibold">Runtime Defaults</h2>
                        <p className="text-sm text-muted-foreground">
                            Choose the provider and saved model or voice you want agents to inherit for each runtime category.
                        </p>
                    </div>
                    <div className="text-xs text-muted-foreground">
                        Recommendations stay visible, but only configured providers can become defaults.
                    </div>
                </div>

                <div className="grid gap-4 xl:grid-cols-2">
                    {DEFAULT_CATEGORIES.map((category) => (
                        <DefaultCategoryCard
                            key={category}
                            category={category}
                            providers={getCategoryProviders(providers, category)}
                        />
                    ))}
                </div>
            </section>

            {providers.length === 0 ? (
                <div className="flex flex-col items-center justify-center rounded-lg border border-dashed py-12 text-center">
                    <p className="text-sm font-medium">No providers configured yet.</p>
                    <p className="mt-2 max-w-md text-sm text-muted-foreground">
                        Add the provider capabilities you want to use, then come back here to choose defaults and manage them as grouped families.
                    </p>
                    <RoleGuard roles={["admin", "developer"]}>
                        <Button variant="outline" size="sm" className="mt-4" onClick={() => setDialogOpen(true)}>
                            <Plus className="mr-2 h-4 w-4" />
                            Add your first provider
                        </Button>
                    </RoleGuard>
                </div>
            ) : (
                <section className="space-y-4">
                    <div>
                        <h2 className="text-xl font-semibold">Provider Families</h2>
                        <p className="text-sm text-muted-foreground">
                            Each card groups the capabilities a provider can own, so one provider can manage STT, LLM, TTS, or telephony without scattering them across the page.
                        </p>
                    </div>

                    <div className="grid gap-4 xl:grid-cols-2">
                        {families.map((family) => (
                            <ProviderFamilyCard key={family.id} family={family} />
                        ))}
                    </div>
                </section>
            )}

            <AddProviderDialog
                open={dialogOpen}
                onOpenChange={setDialogOpen}
                tenantId={tenantId}
                tenantName={tenantName}
            />
        </div>
    );
}

function SummaryCard({
    title,
    value,
    description,
    icon: Icon,
}: {
    title: string;
    value: string;
    description: string;
    icon: ComponentType<{ className?: string }>;
}) {
    return (
        <Card>
            <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
                <div>
                    <CardDescription>{title}</CardDescription>
                    <CardTitle className="text-2xl">{value}</CardTitle>
                </div>
                <Icon className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
                <p className="text-sm text-muted-foreground">{description}</p>
            </CardContent>
        </Card>
    );
}

function DefaultCategoryCard({
    category,
    providers,
}: {
    category: ProviderCategory;
    providers: Provider[];
}) {
    const currentDefault = getDefaultProviderForCategory(providers, category);
    const fallbackProvider = currentDefault ?? providers[0];
    const [selectedProviderId, setSelectedProviderId] = useState(fallbackProvider?.id ?? "");

    const selectedProvider = providers.find((provider) => provider.id === selectedProviderId) ?? fallbackProvider;
    const updateMutation = useUpdateProvider(selectedProvider?.id ?? "");
    const refreshMutation = useRefreshProvider();
    const testMutation = useTestProvider();

    const isBusy = updateMutation.isPending || refreshMutation.isPending || testMutation.isPending;

    return (
        <Card className="border-border/70 shadow-sm">
            <CardHeader className="pb-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                        <CardTitle className="text-lg">{CATEGORY_LABELS[category]}</CardTitle>
                        <CardDescription>
                            Current runtime choice for {CATEGORY_LABELS[category].toLowerCase()} agents and flows.
                        </CardDescription>
                    </div>
                    <Badge variant="outline">Recommended: {getProviderLabel(RECOMMENDED_DEFAULTS[category])}</Badge>
                </div>
            </CardHeader>

            <CardContent className="space-y-4">
                {providers.length === 0 ? (
                    <div className="rounded-lg border border-dashed bg-muted/20 px-4 py-4 text-sm text-muted-foreground">
                        No configured {CATEGORY_LABELS[category].toLowerCase()} provider yet. Add one first, then set it as the runtime default here.
                    </div>
                ) : selectedProvider ? (
                    <>
                        <div className="grid gap-4 md:grid-cols-2">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Provider</label>
                                <select
                                    className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                                    value={selectedProviderId}
                                    onChange={(event) => setSelectedProviderId(event.target.value)}
                                    disabled={isBusy}
                                >
                                    {providers.map((provider) => (
                                        <option key={provider.id} value={provider.id}>
                                            {getProviderLabel(provider.provider_name)} • {getProviderScopeLabel(provider)}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="flex flex-wrap items-start gap-2">
                                <TestStatusBadge status={selectedProvider.test_status} />
                                <Badge variant="outline">{selectedProvider.is_default ? "Current default" : "Not default"}</Badge>
                                <Badge variant="outline">
                                    Last tested: {selectedProvider.last_tested_at ? new Date(selectedProvider.last_tested_at).toLocaleDateString() : "Never"}
                                </Badge>
                            </div>
                        </div>

                        <ProviderConfigEditor
                            key={`${selectedProvider.id}:${selectedProvider.updated_at}`}
                            provider={selectedProvider}
                            isBusy={isBusy}
                            onMakeDefault={() => updateMutation.mutate({ is_default: true })}
                            onRefresh={() => refreshMutation.mutate(selectedProvider.id)}
                            onTest={() => testMutation.mutate(selectedProvider.id)}
                            onSaveSelections={(config) => updateMutation.mutate({ config })}
                            saveLabel="Save Model / Voice"
                        />
                    </>
                ) : null}
            </CardContent>
        </Card>
    );
}

function ProviderFamilyCard({ family }: { family: ProviderFamily }) {
    const categories = DEFAULT_CATEGORIES.filter((category) => family.variants[category]);

    return (
        <Card className="border-border/70 shadow-sm">
            <CardHeader className="pb-3">
                <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-2">
                            <CardTitle className="text-xl">{family.label}</CardTitle>
                            <Badge variant="outline">{family.configuredCount} configured</Badge>
                            {family.defaultCount > 0 ? <Badge variant="secondary">{family.defaultCount} default</Badge> : null}
                            {family.connectedCount > 0 ? <Badge variant="outline" className="border-green-500 text-green-600">{family.connectedCount} connected</Badge> : null}
                        </div>
                        <CardDescription>{family.description}</CardDescription>
                    </div>
                </div>
            </CardHeader>

            <CardContent className="space-y-3">
                {categories.map((category) => {
                    const variantName = family.variants[category];
                    if (!variantName) return null;

                    return (
                        <CapabilityCard
                            key={`${family.id}:${category}`}
                            category={category}
                            providerName={variantName}
                            provider={family.configuredProviders[category]}
                        />
                    );
                })}
            </CardContent>
        </Card>
    );
}

function CapabilityCard({
    category,
    providerName,
    provider,
}: {
    category: ProviderCategory;
    providerName: string;
    provider?: Provider;
}) {
    if (!provider) {
        return (
            <div className="rounded-xl border border-dashed bg-muted/20 px-4 py-4">
                <div className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-semibold">{getProviderLabel(providerName)}</span>
                    <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_COLORS[category]}`}>
                        {CATEGORY_LABELS[category]}
                    </span>
                    {providerName === RECOMMENDED_DEFAULTS[category] ? <Badge variant="outline">Recommended</Badge> : null}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                    This capability is supported by the provider family but is not configured yet. Use Add Provider if you want to activate it for this category.
                </p>
            </div>
        );
    }

    return <ConfiguredCapabilityCard provider={provider} />;
}

function ConfiguredCapabilityCard({ provider }: { provider: Provider }) {
    const updateMutation = useUpdateProvider(provider.id);
    const deleteMutation = useDeleteProvider();
    const testMutation = useTestProvider();
    const refreshMutation = useRefreshProvider();
    const category = provider.provider_category as ProviderCategory;
    const catalog = parseProviderCatalog(provider.config);

    const handleDelete = () => {
        if (confirm(`Delete ${getProviderLabel(provider.provider_name)}?`)) {
            deleteMutation.mutate(provider.id);
        }
    };

    const isBusy =
        updateMutation.isPending || deleteMutation.isPending || testMutation.isPending || refreshMutation.isPending;

    return (
        <div className="rounded-xl border px-4 py-4 shadow-sm">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="text-base font-semibold">{getProviderLabel(provider.provider_name)}</span>
                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${CATEGORY_COLORS[category]}`}>
                            {CATEGORY_LABELS[category]}
                        </span>
                        {provider.is_default ? <Badge variant="secondary">Current default</Badge> : null}
                    </div>
                    <p className="text-sm text-muted-foreground">{getProviderDescription(provider.provider_name)}</p>
                    <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                        <span className="rounded-full border px-3 py-1">{getProviderScopeLabel(provider)}</span>
                        <span className="rounded-full border px-3 py-1">{getCatalogCountLabel(provider)}</span>
                        <span className="rounded-full border px-3 py-1">
                            Last synced: {catalog.refreshed_at ? new Date(catalog.refreshed_at).toLocaleString() : "Never"}
                        </span>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                    <TestStatusBadge status={provider.test_status} />
                    <Badge variant="outline">
                        Last tested: {provider.last_tested_at ? new Date(provider.last_tested_at).toLocaleDateString() : "Never"}
                    </Badge>
                </div>
            </div>
            <ProviderConfigEditor
                key={`${provider.id}:${provider.updated_at}`}
                provider={provider}
                isBusy={isBusy}
                onMakeDefault={() => updateMutation.mutate({ is_default: true })}
                onRefresh={() => refreshMutation.mutate(provider.id)}
                onTest={() => testMutation.mutate(provider.id)}
                onSaveSelections={(config) => updateMutation.mutate({ config })}
                onDelete={handleDelete}
                saveLabel="Save Selections"
            />
        </div>
    );
}

function ProviderConfigEditor({
    provider,
    isBusy,
    onMakeDefault,
    onRefresh,
    onTest,
    onSaveSelections,
    onDelete,
    saveLabel,
}: {
    provider: Provider;
    isBusy: boolean;
    onMakeDefault: () => void;
    onRefresh: () => void;
    onTest: () => void;
    onSaveSelections: (config: Record<string, unknown>) => void;
    onDelete?: () => void;
    saveLabel: string;
}) {
    const models = getProviderModels(provider);
    const voices = getProviderVoices(provider);
    const currentModel = getProviderSelectedModel(provider) ?? "";
    const currentVoice = getProviderSelectedVoice(provider) ?? "";
    const [selectedModel, setSelectedModel] = useState(currentModel);
    const [selectedVoice, setSelectedVoice] = useState(currentVoice);
    const [voiceSearch, setVoiceSearch] = useState("");
    const [voiceLocaleFilter, setVoiceLocaleFilter] = useState("all");
    const [voiceGenderFilter, setVoiceGenderFilter] = useState("all");
    const [voiceTypeFilter, setVoiceTypeFilter] = useState("all");
    const [voiceStyleFilter, setVoiceStyleFilter] = useState("all");
    const hasConfigChanges = selectedModel !== currentModel || selectedVoice !== currentVoice;

    const localeOptions = useMemo(
        () => getSortedUniqueStrings(voices.flatMap((voice) => getVoiceLocaleValues(voice))),
        [voices],
    );
    const genderOptions = useMemo(
        () => getSortedUniqueStrings(voices.map((voice) => voice.gender)),
        [voices],
    );
    const voiceTypeOptions = useMemo(
        () => getSortedUniqueStrings(voices.map((voice) => voice.voice_type)),
        [voices],
    );
    const styleOptions = useMemo(
        () => getSortedUniqueStrings(voices.flatMap((voice) => voice.styles ?? [])),
        [voices],
    );
    const filteredVoices = useMemo(
        () =>
            voices.filter((voice) => {
                const searchNeedle = voiceSearch.trim().toLowerCase();
                if (searchNeedle) {
                    const searchable = [
                        voice.name,
                        voice.id,
                        voice.locale,
                        voice.locale_name,
                        voice.local_name,
                        ...(voice.styles ?? []),
                        ...(voice.secondary_locales ?? []),
                    ]
                        .filter((value): value is string => typeof value === "string" && value.length > 0)
                        .join(" ")
                        .toLowerCase();
                    if (!searchable.includes(searchNeedle)) {
                        return false;
                    }
                }

                if (voiceLocaleFilter !== "all" && !getVoiceLocaleValues(voice).includes(voiceLocaleFilter)) {
                    return false;
                }

                if (voiceGenderFilter !== "all" && voice.gender !== voiceGenderFilter) {
                    return false;
                }

                if (voiceTypeFilter !== "all" && voice.voice_type !== voiceTypeFilter) {
                    return false;
                }

                if (voiceStyleFilter !== "all" && !(voice.styles ?? []).includes(voiceStyleFilter)) {
                    return false;
                }

                return true;
            }),
        [voices, voiceSearch, voiceLocaleFilter, voiceGenderFilter, voiceTypeFilter, voiceStyleFilter],
    );
    const visibleVoices = useMemo(() => {
        const selected = voices.find((voice) => voice.id === selectedVoice);
        if (selected && !filteredVoices.some((voice) => voice.id === selected.id)) {
            return [selected, ...filteredVoices];
        }
        return filteredVoices;
    }, [filteredVoices, selectedVoice, voices]);
    const selectedVoiceItem = useMemo(
        () => voices.find((voice) => voice.id === selectedVoice) ?? null,
        [selectedVoice, voices],
    );

    const handleSaveSelections = () => {
        onSaveSelections({
            ...provider.config,
            ...(selectedModel ? { model: selectedModel } : {}),
            ...(selectedVoice ? { voice_id: selectedVoice } : {}),
        });
    };

    return (
        <div className="mt-4 space-y-4">
            {models.length > 0 || voices.length > 0 ? (
                <div className="grid gap-4 md:grid-cols-2">
                    {models.length > 0 ? (
                        <div className="space-y-2">
                            <label className="text-sm font-medium">Model</label>
                            <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                                value={selectedModel}
                                onChange={(event) => setSelectedModel(event.target.value)}
                                disabled={isBusy}
                            >
                                <option value="">Use provider default</option>
                                {models.map((model) => (
                                    <option key={model.id} value={model.id}>
                                        {model.name}
                                    </option>
                                ))}
                            </select>
                        </div>
                    ) : null}

                    {voices.length > 0 ? (
                        <div className="space-y-3 md:col-span-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <label className="text-sm font-medium">Voice</label>
                                <span className="text-xs text-muted-foreground">
                                    {filteredVoices.length} of {voices.length} voices match
                                </span>
                            </div>
                            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
                                <div className="space-y-2 xl:col-span-2">
                                    <label className="text-xs font-medium text-muted-foreground">Search</label>
                                    <Input
                                        value={voiceSearch}
                                        onChange={(event) => setVoiceSearch(event.target.value)}
                                        placeholder="Search voice, locale, accent, or style"
                                        disabled={isBusy}
                                    />
                                </div>
                                <VoiceFilterSelect
                                    label="Locale"
                                    value={voiceLocaleFilter}
                                    options={localeOptions}
                                    onChange={setVoiceLocaleFilter}
                                    disabled={isBusy}
                                />
                                <VoiceFilterSelect
                                    label="Gender"
                                    value={voiceGenderFilter}
                                    options={genderOptions}
                                    onChange={setVoiceGenderFilter}
                                    disabled={isBusy}
                                />
                                <VoiceFilterSelect
                                    label="Type"
                                    value={voiceTypeFilter}
                                    options={voiceTypeOptions}
                                    onChange={setVoiceTypeFilter}
                                    disabled={isBusy}
                                />
                                <VoiceFilterSelect
                                    label="Style"
                                    value={voiceStyleFilter}
                                    options={styleOptions}
                                    onChange={setVoiceStyleFilter}
                                    disabled={isBusy}
                                />
                            </div>
                            <select
                                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                                value={selectedVoice}
                                onChange={(event) => setSelectedVoice(event.target.value)}
                                disabled={isBusy}
                            >
                                <option value="">Use provider default</option>
                                {visibleVoices.map((voice) => (
                                    <option key={voice.id} value={voice.id}>
                                        {formatVoiceOptionLabel(voice)}
                                    </option>
                                ))}
                            </select>
                            {selectedVoiceItem ? <SelectedVoiceSummary voice={selectedVoiceItem} /> : null}
                        </div>
                    ) : null}
                </div>
            ) : (
                <div className="rounded-lg border border-dashed bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                    This provider has no synced model or voice catalog yet. Refresh it first, then choose saved defaults here.
                </div>
            )}

            <div className="flex flex-wrap gap-2">
                <RoleGuard roles={["admin", "developer"]}>
                    <Button variant="outline" onClick={onMakeDefault} disabled={isBusy || provider.is_default}>
                        <WandSparkles className="mr-2 h-4 w-4" />
                        {provider.is_default ? "Current Default" : "Make Default"}
                    </Button>
                    <Button variant="outline" onClick={onRefresh} disabled={isBusy}>
                        <RefreshCcw className="mr-2 h-4 w-4" />
                        Refresh
                    </Button>
                    <Button variant="outline" onClick={onTest} disabled={isBusy}>
                        <FlaskConical className="mr-2 h-4 w-4" />
                        Test
                    </Button>
                    <Button variant="outline" onClick={handleSaveSelections} disabled={isBusy || !hasConfigChanges}>
                        <Save className="mr-2 h-4 w-4" />
                        {saveLabel}
                    </Button>
                    {onDelete ? (
                        <Button variant="ghost" onClick={onDelete} disabled={isBusy} className="text-destructive hover:text-destructive">
                            <Trash2 className="mr-2 h-4 w-4" />
                            Delete
                        </Button>
                    ) : null}
                </RoleGuard>
            </div>
        </div>
    );
}

function VoiceFilterSelect({
    label,
    value,
    options,
    onChange,
    disabled,
}: {
    label: string;
    value: string;
    options: string[];
    onChange: (value: string) => void;
    disabled: boolean;
}) {
    return (
        <div className="space-y-2">
            <label className="text-xs font-medium text-muted-foreground">{label}</label>
            <select
                className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm"
                value={value}
                onChange={(event) => onChange(event.target.value)}
                disabled={disabled}
            >
                <option value="all">All</option>
                {options.map((option) => (
                    <option key={option} value={option}>
                        {option}
                    </option>
                ))}
            </select>
        </div>
    );
}

function SelectedVoiceSummary({ voice }: { voice: ProviderCatalogItem }) {
    const badges = [
        voice.locale_name ?? voice.locale ?? voice.language,
        voice.gender,
        voice.voice_type,
        voice.status,
        voice.sample_rate_hertz ? `${voice.sample_rate_hertz} Hz` : undefined,
        voice.words_per_minute ? `${voice.words_per_minute} wpm` : undefined,
    ].filter((value): value is string => typeof value === "string" && value.length > 0);

    return (
        <div className="rounded-lg border bg-muted/20 px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{voice.name}</span>
                <span className="text-muted-foreground">{voice.id}</span>
            </div>
            {voice.local_name && voice.local_name !== voice.name ? (
                <p className="mt-1 text-muted-foreground">Local name: {voice.local_name}</p>
            ) : null}
            {badges.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-2">
                    {badges.map((badge) => (
                        <Badge key={badge} variant="outline">
                            {badge}
                        </Badge>
                    ))}
                </div>
            ) : null}
            {voice.secondary_locales?.length ? (
                <p className="mt-2 text-muted-foreground">
                    Multilingual accents/locales: {voice.secondary_locales.join(", ")}
                </p>
            ) : null}
            {voice.styles?.length ? (
                <p className="mt-2 text-muted-foreground">Styles: {voice.styles.join(", ")}</p>
            ) : null}
            {voice.tags?.length ? (
                <p className="mt-2 text-muted-foreground">Tags: {voice.tags.join(", ")}</p>
            ) : null}
            {voice.roles?.length ? (
                <p className="mt-2 text-muted-foreground">Roles: {voice.roles.join(", ")}</p>
            ) : null}
        </div>
    );
}

function getSortedUniqueStrings(values: Array<string | undefined>): string[] {
    return Array.from(
        new Set(values.filter((value): value is string => typeof value === "string" && value.length > 0)),
    ).sort((left, right) => left.localeCompare(right));
}

function getVoiceLocaleValues(voice: ProviderCatalogItem): string[] {
    return getSortedUniqueStrings([
        voice.locale,
        voice.language,
        ...(voice.secondary_locales ?? []),
    ]);
}

function formatVoiceOptionLabel(voice: ProviderCatalogItem): string {
    const details = [voice.locale ?? voice.language, voice.gender].filter(
        (value): value is string => typeof value === "string" && value.length > 0,
    );
    return details.length > 0 ? `${voice.name} (${details.join(" • ")})` : voice.name;
}
