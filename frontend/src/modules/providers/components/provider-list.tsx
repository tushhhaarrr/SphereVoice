"use client";

import React, { useMemo, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useProviderCapabilities, ProviderCapability } from "../hooks/use-capabilities";
import { 
    CheckCircle2, 
    XCircle, 
    BrainCircuit, 
    Mic, 
    AudioLines, 
    PhoneCall,
    Search,
    Settings2,
    DatabaseZap,
    AlertCircle,
    Activity,
    ChevronRight,
    TerminalSquare
} from "lucide-react";

export function ProviderList() {
    const { data: capabilities, isLoading, isError } = useProviderCapabilities();
    const [search, setSearch] = useState("");
    const [filterType, setFilterType] = useState<string>("all");

    const filteredProviders = useMemo(() => {
        if (!capabilities) return [];
        return capabilities.filter(c => {
            const matchesSearch = c.name.toLowerCase().includes(search.toLowerCase());
            const matchesType = filterType === "all" || c.type === filterType;
            return matchesSearch && matchesType;
        });
    }, [capabilities, search, filterType]);

    const activeCount = capabilities?.filter(c => c.is_active).length || 0;

    if (isLoading) {
        return (
            <div className="flex h-96 items-center justify-center space-x-2">
                <Activity className="h-6 w-6 animate-pulse text-indigo-500" />
                <span className="text-sm font-medium text-slate-500 dark:text-slate-400">Discovering architectural providers...</span>
            </div>
        );
    }

    if (isError) {
        return (
            <div className="flex h-96 flex-col items-center justify-center space-y-4">
                <AlertCircle className="h-12 w-12 text-red-500" />
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Substrate Disconnected</h3>
                <p className="text-sm text-slate-500">Failed to connect to the Provider Registry.</p>
            </div>
        );
    }

    return (
        <div className="flex w-full flex-col space-y-8 p-6 md:p-8">
            <div className="flex flex-col space-y-4 md:flex-row md:items-end md:justify-between md:space-y-0">
                <div className="flex flex-col space-y-1">
                    <h1 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-white">Provider Architecture</h1>
                    <p className="text-base text-slate-500 dark:text-slate-400">
                        Manage cognitive models, speech synthesis, and telephony egress conduits.
                    </p>
                </div>
                
                <div className="flex items-center space-x-4 rounded-xl border border-slate-200 bg-white p-2 shadow-sm dark:border-slate-800 dark:bg-slate-900">
                    <div className="flex items-center space-x-2 px-3 border-r border-slate-200 dark:border-slate-800">
                        <DatabaseZap className="h-5 w-5 text-emerald-500" />
                        <div className="flex flex-col">
                            <span className="text-xs font-semibold text-slate-900 dark:text-white">Active Nodes</span>
                            <span className="text-[10px] text-slate-500">{activeCount} / {capabilities?.length} Online</span>
                        </div>
                    </div>
                    <button className="flex items-center space-x-2 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-indigo-700 hover:shadow-md">
                        <Settings2 className="h-4 w-4" />
                        <span>Manage Keys</span>
                    </button>
                </div>
            </div>

            <div className="flex flex-col space-y-4 md:flex-row md:items-center md:space-x-4 md:space-y-0">
                <div className="relative flex-1">
                    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
                    <input
                        type="text"
                        placeholder="Search provider taxonomy..."
                        className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-4 text-sm outline-none transition-all focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 dark:border-slate-800 dark:bg-slate-900 dark:text-white dark:focus:border-indigo-500"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>
                <div className="flex space-x-2">
                    {["all", "llm", "voice", "stt", "telephony"].map((type) => (
                        <button
                            key={type}
                            onClick={() => setFilterType(type)}
                            className={`rounded-lg px-4 py-2 text-sm font-medium capitalize transition-all ${
                                filterType === type 
                                    ? "bg-slate-900 text-white shadow-md dark:bg-white dark:text-slate-900" 
                                    : "bg-white text-slate-600 border border-slate-200 hover:bg-slate-50 dark:bg-slate-900 dark:border-slate-800 dark:text-slate-400 dark:hover:bg-slate-800"
                            }`}
                        >
                            {type === "stt" ? "Perception" : type === "llm" ? "Cognitive" : type === "voice" ? "Synthesis" : type === "telephony" ? "Transport" : "All"}
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                <AnimatePresence>
                    {filteredProviders?.map((provider) => (
                        <ProviderCard key={provider.id} provider={provider} />
                    ))}
                </AnimatePresence>
            </div>

            {filteredProviders?.length === 0 && (
                <div className="flex w-full flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 py-16 dark:border-slate-800">
                    <TerminalSquare className="mb-4 h-12 w-12 text-slate-300 dark:text-slate-700" />
                    <h3 className="text-lg font-medium text-slate-900 dark:text-white">No providers mapped</h3>
                    <p className="text-sm text-slate-500">Try adjusting your taxonomy filters.</p>
                </div>
            )}
        </div>
    );
}

function ProviderCard({ provider }: { provider: ProviderCapability }) {
    const iconMap = {
        llm: BrainCircuit,
        stt: Mic,
        voice: AudioLines,
        telephony: PhoneCall
    };
    
    const Icon = iconMap[provider.type] || Settings2;
    const isDemo = provider.id.startsWith("demo-");

    return (
        <motion.div
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className={`group relative flex cursor-pointer flex-col overflow-hidden rounded-2xl border transition-all hover:-translate-y-1 hover:shadow-xl ${
                provider.is_active 
                    ? "border-slate-200 bg-white hover:border-indigo-300 dark:border-slate-800 dark:bg-slate-900/80 dark:hover:border-indigo-500/50" 
                    : "border-slate-200 bg-slate-50/50 hover:border-slate-300 dark:border-slate-800/80 dark:bg-slate-900/40 dark:hover:border-slate-700"
            }`}
        >
            <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/5 to-purple-500/5 opacity-0 transition-opacity group-hover:opacity-100" />
            
            <div className="flex flex-1 flex-col p-6 z-10">
                <div className="mb-4 flex items-start justify-between">
                    <div className={`flex h-12 w-12 items-center justify-center rounded-xl border ${
                        provider.is_active 
                            ? isDemo ? "border-amber-200 bg-amber-50 text-amber-600 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-400" : "border-indigo-100 bg-indigo-50 text-indigo-600 dark:border-indigo-900/50 dark:bg-indigo-900/20 dark:text-indigo-400"
                            : "border-slate-200 bg-white text-slate-400 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-500"
                    }`}>
                        <Icon className="h-6 w-6" />
                    </div>
                    
                    {provider.is_active ? (
                        <span className={`inline-flex items-center space-x-1 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                            isDemo ? "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400" : "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                        }`}>
                            <CheckCircle2 className="mr-1 h-3 w-3" />
                            {isDemo ? "Demo Mode" : "Connected"}
                        </span>
                    ) : (
                        <span className="inline-flex items-center space-x-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                            <XCircle className="mr-1 h-3 w-3" />
                            Missing Key
                        </span>
                    )}
                </div>

                <h3 className="mb-1 text-lg font-bold text-slate-900 dark:text-white group-hover:text-indigo-600 dark:group-hover:text-indigo-400 transition-colors">
                    {provider.name}
                </h3>
                
                <p className="mb-6 text-xs text-slate-500 dark:text-slate-400">
                    {provider.env_var_key ? `Requires ${provider.env_var_key}` : "Pre-configured environment"}
                </p>

                <div className="mt-auto flex flex-col space-y-3 border-t border-slate-100 pt-4 dark:border-slate-800">
                    <div className="flex items-center justify-between text-xs">
                        <span className="text-slate-500 dark:text-slate-400">Available Models</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{provider.models.length}</span>
                    </div>
                    {provider.type === "voice" && (
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-slate-500 dark:text-slate-400">Voice Synthesis Profiles</span>
                            <span className="font-semibold text-slate-900 dark:text-white">{provider.voices.length}</span>
                        </div>
                    )}
                </div>
            </div>

            <div className={`absolute bottom-0 left-0 h-1 w-full transition-all duration-300 ${
                provider.is_active 
                    ? isDemo ? "bg-amber-500 scale-x-100" : "bg-emerald-500 scale-x-0 group-hover:scale-x-100" 
                    : "bg-slate-200 dark:bg-slate-800 scale-x-0"
            }`} />
        </motion.div>
    );
}
