import type {
  IntegrationStatus,
  IntegrationCategory,
  CategoryMeta,
} from "../types";

// ─── Status Colors ───────────────────────────────────────────────────────────

const INTEGRATION_STATUS_COLORS: Record<
  IntegrationStatus,
  { bg: string; text: string; dot: string }
> = {
  active: {
    bg: "bg-green-50",
    text: "text-green-700",
    dot: "bg-green-500",
  },
  inactive: {
    bg: "bg-gray-100",
    text: "text-gray-700",
    dot: "bg-gray-400",
  },
  error: {
    bg: "bg-red-50",
    text: "text-red-700",
    dot: "bg-red-500",
  },
};

export function getIntegrationStatusColor(status: IntegrationStatus) {
  return INTEGRATION_STATUS_COLORS[status] ?? INTEGRATION_STATUS_COLORS.inactive;
}

// ─── Status Labels ───────────────────────────────────────────────────────────

const INTEGRATION_STATUS_LABELS: Record<IntegrationStatus, string> = {
  active: "Connected",
  inactive: "Disconnected",
  error: "Error",
};

export function getIntegrationStatusLabel(status: IntegrationStatus): string {
  return INTEGRATION_STATUS_LABELS[status] ?? status;
}

// ─── Category Metadata ───────────────────────────────────────────────────────

export const INTEGRATION_CATEGORIES: CategoryMeta[] = [
  {
    key: "crm",
    label: "CRM",
    description: "Connect your CRM to sync contacts and write back call data",
    providers: [
      {
        value: "zoho_crm",
        label: "Zoho CRM",
        description: "Read contacts, write-back fields after calls",
      },
      {
        value: "hubspot",
        label: "HubSpot",
        description: "Sync HubSpot contacts and deals",
      },
      {
        value: "salesforce",
        label: "Salesforce",
        description: "Sync Salesforce contacts, leads and opportunities",
      },
    ],
  },
  {
    key: "calendar",
    label: "Calendar",
    description: "Schedule meetings during or after calls",
    providers: [
      {
        value: "cal_com",
        label: "Cal.com",
        description: "Book meetings via Cal.com scheduling links",
      },
      {
        value: "calendly",
        label: "Calendly",
        description: "Book meetings via Calendly",
      },
    ],
  },
  {
    key: "messaging",
    label: "Messaging",
    description: "Send messages, links, and confirmations via SMS or WhatsApp",
    providers: [
      {
        value: "whatsapp_cloud",
        label: "WhatsApp Cloud API",
        description: "Send WhatsApp messages and templates",
      },
      {
        value: "twilio_sms",
        label: "Twilio SMS",
        description: "Send SMS messages via Twilio",
      },
    ],
  },
  {
    key: "email",
    label: "Email",
    description: "Send follow-up emails after calls",
    providers: [
      {
        value: "sendgrid",
        label: "SendGrid",
        description: "Transactional and marketing emails",
      },
      {
        value: "postmark",
        label: "Postmark",
        description: "Transactional email delivery",
      },
      {
        value: "smtp",
        label: "SMTP",
        description: "Generic SMTP email server",
      },
    ],
  },
  {
    key: "custom_webhook",
    label: "Custom Webhook",
    description: "Generic HTTP endpoint for custom agent tools",
    providers: [
      {
        value: "custom",
        label: "Custom URL",
        description: "Any HTTP endpoint your agents can call",
      },
    ],
  },
];

export function getCategoryMeta(
  category: IntegrationCategory
): CategoryMeta | undefined {
  return INTEGRATION_CATEGORIES.find((c) => c.key === category);
}

export function getProviderLabel(provider: string): string {
  for (const cat of INTEGRATION_CATEGORIES) {
    const p = cat.providers.find((pr) => pr.value === provider);
    if (p) return p.label;
  }
  return provider;
}

export function getCategoryLabel(category: string): string {
  const meta = INTEGRATION_CATEGORIES.find((c) => c.key === category);
  return meta?.label ?? category;
}

// ─── Formatting Helpers ──────────────────────────────────────────────────────

export function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString();
}

export function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.floor(diff / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
