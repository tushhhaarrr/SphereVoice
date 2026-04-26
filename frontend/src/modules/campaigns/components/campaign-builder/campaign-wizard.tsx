"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ChevronLeft, ChevronRight, Rocket } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useCreateCampaign } from "../../hooks/use-campaigns";
import type { CampaignWizardData } from "../../types";
import { WIZARD_STEPS } from "../../types";
import { StepAgentSelect } from "./step-agent-select";
import { StepCrmSource } from "./step-crm-source";
import { StepVariableMapping } from "./step-variable-mapping";
import { StepWritebackMapping } from "./step-writeback-mapping";
import { StepCallSettings } from "./step-call-settings";
import { StepAbTest } from "./step-ab-test";
import { StepToolConfig } from "./step-tool-config";
import { StepReview } from "./step-review";

interface CampaignWizardProps {
  tenantId: string;
}

const DEFAULT_WIZARD_DATA: CampaignWizardData = {
  agent_id: "",
  source_type: "manual",
  source_config: {},
  variable_mapping: {},
  writeback_mapping: {},
  name: "",
  description: "",
  from_number: "",
  max_concurrent: 5,
  calls_per_minute: 10,
  max_retries: 2,
  retry_delay_minutes: 30,
  scheduled_at: null,
  calling_window: null,
  tool_config: {},
  variant_agent_id: "",
  ab_split_percent: 50,
};

export function CampaignWizard({ tenantId }: CampaignWizardProps) {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [data, setData] = useState<CampaignWizardData>(DEFAULT_WIZARD_DATA);
  const createCampaign = useCreateCampaign(tenantId);

  const totalSteps = WIZARD_STEPS.length;
  const isFirstStep = currentStep === 0;
  const isLastStep = currentStep === totalSteps - 1;

  function handleUpdate(partial: Partial<CampaignWizardData>) {
    setData((prev) => ({ ...prev, ...partial }));
  }

  function handleBack() {
    if (!isFirstStep) setCurrentStep((s) => s - 1);
  }

  function handleNext() {
    if (!isLastStep) setCurrentStep((s) => s + 1);
  }

  async function handleSubmit() {
    if (!data.agent_id || !data.name) return;

    // Clean up view_id if it's "__all__" (meaning no filter)
    const sourceConfig = { ...data.source_config };
    if (sourceConfig.view_id === "__all__") {
      delete sourceConfig.view_id;
    }

    const payload = {
      name: data.name,
      description: data.description || undefined,
      agent_id: data.agent_id,
      source_type: data.source_type,
      source_config: sourceConfig,
      variable_mapping: data.variable_mapping,
      writeback_mapping: data.writeback_mapping,
      from_number: data.from_number || undefined,
      max_concurrent: data.max_concurrent,
      calls_per_minute: data.calls_per_minute,
      max_retries: data.max_retries,
      retry_delay_minutes: data.retry_delay_minutes,
      scheduled_at: data.scheduled_at ?? undefined,
      calling_window: data.calling_window ?? undefined,
      variant_agent_id: data.variant_agent_id || undefined,
      ab_split_percent: data.variant_agent_id ? data.ab_split_percent : undefined,
    };

    const campaign = await createCampaign.mutateAsync(payload);

    // Auto-load contacts from CRM if source is zoho_crm
    if ((data.source_type === "crm" || data.source_type === "zoho_crm") && sourceConfig.module) {
      try {
        const { fetchWithAuth } = await import("@/lib/api-client");
        const qs = tenantId ? `?tenant_id=${tenantId}` : "";
        await fetchWithAuth(
          `/api/v1/campaigns/${campaign.id}/load-from-crm${qs}`,
          { method: "POST" }
        );
      } catch {
        // Contacts can be loaded later from the dashboard
      }
    }

    router.push(`/workspace/${tenantId}/campaigns/${campaign.id}`);
  }

  const canProceed =
    currentStep === 0 ? !!data.agent_id : currentStep === 4 ? !!data.name : true;

  function renderStep() {
    switch (currentStep) {
      case 0:
        return (
          <StepAgentSelect
            data={data}
            onUpdate={handleUpdate}
            tenantId={tenantId}
          />
        );
      case 1:
        return (
          <StepCrmSource
            data={data}
            onUpdate={handleUpdate}
            tenantId={tenantId}
          />
        );
      case 2:
        return (
          <StepVariableMapping
            data={data}
            onUpdate={handleUpdate}
            tenantId={tenantId}
          />
        );
      case 3:
        return (
          <StepWritebackMapping
            data={data}
            onUpdate={handleUpdate}
            tenantId={tenantId}
          />
        );
      case 4:
        return <StepCallSettings data={data} onUpdate={handleUpdate} />;
      case 5:
        return (
          <StepAbTest
            data={data}
            onUpdate={handleUpdate}
            tenantId={tenantId}
          />
        );
      case 6:
        return <StepToolConfig data={data} onUpdate={handleUpdate} />;
      case 7:
        return <StepReview data={data} tenantId={tenantId} />;
      default:
        return null;
    }
  }

  return (
    <div className="space-y-6">
      {/* Stepper */}
      <div className="flex items-center gap-1">
        {WIZARD_STEPS.map((step, idx) => (
          <div key={step.key} className="flex items-center">
            <button
              type="button"
              onClick={() => idx < currentStep && setCurrentStep(idx)}
              disabled={idx > currentStep}
              className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${idx === currentStep
                ? "bg-primary text-primary-foreground"
                : idx < currentStep
                  ? "bg-muted text-foreground hover:bg-muted/80 cursor-pointer"
                  : "text-muted-foreground cursor-not-allowed"
                }`}
            >
              <span className="flex h-5 w-5 items-center justify-center rounded-full bg-background/20 text-xs">
                {idx + 1}
              </span>
              <span className="hidden md:inline">{step.label}</span>
            </button>
            {idx < totalSteps - 1 && (
              <div className="mx-1 h-px w-4 bg-border" />
            )}
          </div>
        ))}
      </div>

      {/* Step Content */}
      <Card>
        <CardContent className="pt-6">{renderStep()}</CardContent>
      </Card>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <Button
          variant="outline"
          onClick={handleBack}
          disabled={isFirstStep}
        >
          <ChevronLeft className="mr-1 h-4 w-4" />
          Back
        </Button>

        {isLastStep ? (
          <Button
            onClick={handleSubmit}
            disabled={
              !data.agent_id ||
              !data.name ||
              createCampaign.isPending
            }
          >
            {createCampaign.isPending ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <Rocket className="mr-2 h-4 w-4" />
            )}
            Create Campaign
          </Button>
        ) : (
          <Button onClick={handleNext} disabled={!canProceed}>
            Next
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        )}
      </div>

      {createCampaign.isError && (
        <p className="text-sm text-destructive">
          {createCampaign.error.message}
        </p>
      )}
    </div>
  );
}
