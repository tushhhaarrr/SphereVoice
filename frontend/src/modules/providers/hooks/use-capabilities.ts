import { useQuery } from "@tanstack/react-query";
import { fetchWithAuth } from "@/lib/api-client";

export interface ProviderCapability {
    id: string;
    name: string;
    type: "llm" | "voice" | "stt" | "telephony";
    models: string[];
    voices: string[];
    supported_languages: string[];
    is_active: boolean;
    env_var_key: string | null;
}

export function useProviderCapabilities() {
    return useQuery<ProviderCapability[]>({
        queryKey: ["provider_capabilities"],
        queryFn: async () => {
            const res = await fetchWithAuth("/api/v1/providers/capabilities");
            if (!res.ok) throw new Error("Failed to fetch provider capabilities");
            return res.json();
        },
    });
}
