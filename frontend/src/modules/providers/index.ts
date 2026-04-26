/**
 * Providers Module — Public API
 */

// Components
export { ProviderList } from "./components/provider-list";
export { AddProviderDialog } from "./components/add-provider-dialog";

// Hooks
export {
    useProviders,
    useProvidersList,
    useProvider,
    useCreateProvider,
    useUpdateProvider,
    useDeleteProvider,
    useTestProvider,
    useRefreshProvider,
} from "./hooks/use-providers";

// Catalog helpers
export {
    CATEGORY_COLORS,
    CATEGORY_LABELS,
    PROVIDER_FAMILY_OPTIONS,
    PROVIDER_OPTIONS,
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
    normalizeProviderName,
    parseProviderCatalog,
} from "./lib/catalog";

// Types
export type {
    Provider,
    ProviderCategory,
    ProviderCreateRequest,
    ProviderUpdateRequest,
    ProviderTestResponse,
    ProviderListResponse,
} from "./types";
