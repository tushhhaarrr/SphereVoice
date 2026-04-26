"use client";

/**
 * IntegrationsPage — top-level component rendered inside the tenant workspace.
 *
 * Shows available third-party integrations grouped by category.
 * Currently supports Zoho CRM; designed to be extended with more providers.
 */

import { useEffect, useState } from "react";
import { useSearchParams, useRouter, usePathname, useParams } from "next/navigation";
import { CheckCircle2, Puzzle, Users, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCrmIntegrations, useTenantIntegrations } from "../hooks/use-integrations";
import {
  useGoogleCalendarIntegrations,
  useGoogleSheetsIntegrations,
} from "../hooks/use-google-integrations";
import { useCalendlyIntegrations } from "../hooks/use-calendly-integrations";
import { CrmSettingsPanel } from "./crm-settings-panel";
import { CrmSyncStatusPanel } from "./crm-sync-status-panel";
import { ZohoCrmCard } from "./zoho-crm-card";
import { HubSpotCrmCard } from "./hubspot-crm-card";
import { SalesforceCrmCard } from "./salesforce-crm-card";
import { GoogleCalendarCard } from "./google-calendar-card";
import { GoogleSheetsCard } from "./google-sheets-card";
import { CalendlyCard } from "./calendly-card";
import { WhatsAppCard } from "./whatsapp-card";
import { EmailCard } from "./email-card";
import IntegrationSettingsPage from "./integration-settings";

export function IntegrationsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ tenantId: string }>();
  const tenantId = params.tenantId;
  const { data, isLoading } = useCrmIntegrations(tenantId);
  const { data: calendarData, isLoading: calendarLoading } = useGoogleCalendarIntegrations(tenantId);
  const { data: sheetsData, isLoading: sheetsLoading } = useGoogleSheetsIntegrations(tenantId);
  const { data: calendlyData, isLoading: calendlyLoading } = useCalendlyIntegrations(tenantId);
  const { data: tenantIntegrationsData } = useTenantIntegrations(tenantId);
  const [banner, setBanner] = useState<{ type: "success" | "error"; message: string } | null>(null);

  // Handle OAuth redirect feedback from URL params
  useEffect(() => {
    const hubspotConnected = searchParams.get("hubspot_connected");
    const hubspotError = searchParams.get("hubspot_error");
    const salesforceConnected = searchParams.get("salesforce_connected");
    const salesforceError = searchParams.get("salesforce_error");
    const googleCalendarConnected = searchParams.get("google_calendar_connected");
    const googleSheetsConnected = searchParams.get("google_sheets_connected");
    const googleError = searchParams.get("google_error");
    const calendlyConnected = searchParams.get("calendly_connected");
    const calendlyError = searchParams.get("calendly_error");
    const zohoConnected = searchParams.get("zoho_connected") || searchParams.get("crm_connected");
    const zohoError = searchParams.get("zoho_error") || searchParams.get("crm_error");

    if (zohoConnected === "true") {
      setBanner({ type: "success", message: "CRM connected successfully!" });
      const url = new URL(window.location.href);
      url.searchParams.delete("zoho_connected");
      url.searchParams.delete("crm_connected");
      window.history.replaceState({}, "", url.toString());
    }
    if (hubspotConnected === "true") {
      setBanner({ type: "success", message: "HubSpot CRM connected successfully!" });
      const url = new URL(window.location.href);
      url.searchParams.delete("hubspot_connected");
      window.history.replaceState({}, "", url.toString());
    }
    if (salesforceConnected === "true") {
      setBanner({ type: "success", message: "Salesforce connected successfully!" });
      const url = new URL(window.location.href);
      url.searchParams.delete("salesforce_connected");
      window.history.replaceState({}, "", url.toString());
    }
    if (zohoError) {
      setBanner({
        type: "error",
        message:
          zohoError === "cancelled"
            ? "CRM connection was cancelled."
            : "Failed to connect CRM. Please try again.",
      });
      const url = new URL(window.location.href);
      url.searchParams.delete("zoho_error");
      url.searchParams.delete("crm_error");
      window.history.replaceState({}, "", url.toString());
    }
    if (hubspotError) {
      setBanner({
        type: "error",
        message:
          hubspotError === "cancelled"
            ? "HubSpot connection was cancelled."
            : "Failed to connect HubSpot. Please try again.",
      });
      const url = new URL(window.location.href);
      url.searchParams.delete("hubspot_error");
      window.history.replaceState({}, "", url.toString());
    }
    if (salesforceError) {
      setBanner({
        type: "error",
        message:
          salesforceError === "cancelled"
            ? "Salesforce connection was cancelled."
            : "Failed to connect Salesforce. Please try again.",
      });
      const url = new URL(window.location.href);
      url.searchParams.delete("salesforce_error");
      window.history.replaceState({}, "", url.toString());
    }
    if (googleCalendarConnected === "true") {
      setBanner({ type: "success", message: "Google Calendar connected successfully!" });
      const url = new URL(window.location.href);
      url.searchParams.delete("google_calendar_connected");
      window.history.replaceState({}, "", url.toString());
    }
    if (googleSheetsConnected === "true") {
      setBanner({ type: "success", message: "Google Sheets connected successfully!" });
      const url = new URL(window.location.href);
      url.searchParams.delete("google_sheets_connected");
      window.history.replaceState({}, "", url.toString());
    }
    if (googleError) {
      setBanner({
        type: "error",
        message:
          googleError === "cancelled"
            ? "Google connection was cancelled."
            : "Failed to connect Google. Please try again.",
      });
      const url = new URL(window.location.href);
      url.searchParams.delete("google_error");
      window.history.replaceState({}, "", url.toString());
    }
    if (calendlyConnected === "true") {
      setBanner({ type: "success", message: "Calendly connected successfully!" });
      const url = new URL(window.location.href);
      url.searchParams.delete("calendly_connected");
      window.history.replaceState({}, "", url.toString());
    }
    if (calendlyError) {
      setBanner({
        type: "error",
        message:
          calendlyError === "cancelled"
            ? "Calendly connection was cancelled."
            : "Failed to connect Calendly. Please try again.",
      });
      const url = new URL(window.location.href);
      url.searchParams.delete("calendly_error");
      window.history.replaceState({}, "", url.toString());
    }
  }, [searchParams]);

  const zohoIntegration = data?.integrations.find((i) => i.provider === "zoho_crm");
  const hubspotIntegration = data?.integrations.find((i) => i.provider === "hubspot");
  const salesforceIntegration = data?.integrations.find((i) => i.provider === "salesforce");
  const calendarIntegration = calendarData?.integrations?.[0];
  const sheetsIntegration = sheetsData?.integrations?.[0];
  const calendlyIntegration = calendlyData?.integrations?.[0];
  const whatsappIntegration = tenantIntegrationsData?.integrations.find(
    (i) => i.provider === "whatsapp" && i.category === "messaging"
  );
  const emailIntegration = tenantIntegrationsData?.integrations.find(
    (i) => i.provider === "sendgrid" && i.category === "email"
  );

  return (
    <div className="space-y-8">
      {/* OAuth feedback banner */}
      {banner && (
        <div
          className={`flex items-center gap-2 rounded-md border px-4 py-3 text-sm ${banner.type === "success"
            ? "border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
            : "border-red-200 bg-red-50 text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200"
            }`}
        >
          {banner.type === "success" ? (
            <CheckCircle2 className="h-4 w-4 shrink-0" />
          ) : (
            <XCircle className="h-4 w-4 shrink-0" />
          )}
          <span>{banner.message}</span>
          <button
            className="ml-auto text-current opacity-60 hover:opacity-100"
            onClick={() => setBanner(null)}
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-3">
        <Puzzle className="h-6 w-6 text-primary" />
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Integrations</h1>
          <p className="text-sm text-muted-foreground">
            Connect your CRM and other tools to automate workflows with voice agents.
          </p>
        </div>
      </div>

      {/* CRM section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">CRM</h2>
          <p className="text-xs text-muted-foreground">
            Sync contacts, leads, and deals with your agents.
          </p>
        </div>

        {isLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {/* Skeleton card */}
            <div className="h-48 rounded-xl border bg-muted/40 animate-pulse" />
          </div>
        ) : (
          <>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <ZohoCrmCard integration={zohoIntegration} tenantId={tenantId} />
              <HubSpotCrmCard integration={hubspotIntegration} tenantId={tenantId} />
              <SalesforceCrmCard integration={salesforceIntegration} tenantId={tenantId} />
            </div>

            {/* CRM data shortcut when connected */}
            {(zohoIntegration?.status === "connected" ||
              hubspotIntegration?.status === "connected" ||
              salesforceIntegration?.status === "connected") && (
                <Button
                  variant="outline"
                  className="gap-2 mt-2"
                  onClick={() => router.push(`${pathname}/crm`)}
                >
                  <Users className="h-4 w-4" />
                  View CRM Contacts &amp; Leads
                </Button>
              )}
          </>
        )}
      </section>

      {/* CRM Settings — visible when connected */}
      {(zohoIntegration?.status === "connected" ||
        hubspotIntegration?.status === "connected" ||
        salesforceIntegration?.status === "connected") && (
          <section className="space-y-4">
            <div>
              <h2 className="text-lg font-medium">CRM Settings</h2>
              <p className="text-xs text-muted-foreground">
                Configure phone normalization, field mappings, and auto-create behaviour.
              </p>
            </div>
            <CrmSyncStatusPanel tenantId={tenantId} />
            <CrmSettingsPanel tenantId={tenantId} />
          </section>
        )}

      {/* Calendar section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">Calendar</h2>
          <p className="text-xs text-muted-foreground">
            Book appointments and check availability during live calls.
          </p>
        </div>

        {calendarLoading || calendlyLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="h-48 rounded-xl border bg-muted/40 animate-pulse" />
            <div className="h-48 rounded-xl border bg-muted/40 animate-pulse" />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <GoogleCalendarCard integration={calendarIntegration} tenantId={tenantId} />
            <CalendlyCard integration={calendlyIntegration} tenantId={tenantId} />
          </div>
        )}
      </section>

      {/* Spreadsheets section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">Spreadsheets</h2>
          <p className="text-xs text-muted-foreground">
            Log call data, leads, and extracted fields to Google Sheets automatically.
          </p>
        </div>

        {sheetsLoading ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="h-48 rounded-xl border bg-muted/40 animate-pulse" />
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <GoogleSheetsCard integration={sheetsIntegration} tenantId={tenantId} />
          </div>
        )}
      </section>

      {/* Messaging section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">Messaging</h2>
          <p className="text-xs text-muted-foreground">
            Send WhatsApp messages to callers during live calls.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <WhatsAppCard integration={whatsappIntegration} tenantId={tenantId} />
        </div>
      </section>

      {/* Email section */}
      <section className="space-y-4">
        <div>
          <h2 className="text-lg font-medium">Email</h2>
          <p className="text-xs text-muted-foreground">
            Send emails to callers during or after calls.
          </p>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <EmailCard integration={emailIntegration} tenantId={tenantId} />
        </div>
      </section>

      {/* All tenant integrations — CRUD table */}
      <section className="space-y-4">
        <IntegrationSettingsPage />
      </section>
    </div>
  );
}
