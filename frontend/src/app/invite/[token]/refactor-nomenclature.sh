#!/bin/bash
# Phase 1: Safe Monorepo Nomenclature Refactor
# Executes global find-and-replace for legacy naming without breaking database bindings.

echo "Starting Enterprise SaaS Nomenclature Migration..."

OS_TYPE=$(uname)

function safe_replace() {
    local search=$1
    local replace=$2
    echo "Refactoring '$search' -> '$replace'..."
    
    if [[ "$OS_TYPE" == "Darwin" ]]; then
        # macOS requires an empty extension string for -i
        find ./frontend/src ./backend/app ./packages -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.py" -o -name "*.json" \) -exec sed -i '' "s/$search/$replace/g" {} +
    else
        find ./frontend/src ./backend/app ./packages -type f \( -name "*.ts" -o -name "*.tsx" -o -name "*.py" -o -name "*.json" \) -exec sed -i "s/$search/$replace/g" {} +
    fi
}

# 1. Authentication & Identity
safe_replace "IdentityAlignment" "Authentication"
safe_replace "identity_alignment" "authentication"

# 2. Agents & Voice Engine
safe_replace "NodalEngineering" "Agents"
safe_replace "nodal_engineering" "agents"
safe_replace "SignalSynchronisation" "VoiceEngine"
safe_replace "signal_synchronisation" "voice_engine"

# 3. Providers & Knowledge Base
safe_replace "ResolutionVectors" "KnowledgeBase"
safe_replace "resolution_vectors" "knowledge_base"
safe_replace "CognitiveLibrary" "KnowledgeBase"
safe_replace "SignalHub" "Providers"
safe_replace "signal_hub" "providers"

# 4. Analytics, Webhooks, Integrations & Phone Numbers
safe_replace "ObservabilityTelemetryNexus" "Analytics"
safe_replace "IngressConduitManagement" "PhoneNumbers"
safe_replace "EgressConduitResolution" "Integrations"
safe_replace "SyncJunction" "Webhooks"
safe_replace "SignalPropagation" "Campaigns"
safe_replace "SpectralBenchmarks" "Billing"

echo "Refactor complete. Please run your linter/type-checker to catch any edge cases."
echo "pnpm type-check && cd backend && mypy ."