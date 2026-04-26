import type {
  CampaignStatus,
  CampaignContactStatus,
  WritebackStatus,
} from "../types";

// ─── Status Colors ───────────────────────────────────────────────────────────

const CAMPAIGN_STATUS_COLORS: Record<
  CampaignStatus,
  { bg: string; text: string; dot: string }
> = {
  draft: { bg: "bg-gray-100", text: "text-gray-700", dot: "bg-gray-400" },
  loading_contacts: {
    bg: "bg-blue-50",
    text: "text-blue-700",
    dot: "bg-blue-400",
  },
  ready: {
    bg: "bg-emerald-50",
    text: "text-emerald-700",
    dot: "bg-emerald-400",
  },
  scheduled: {
    bg: "bg-purple-50",
    text: "text-purple-700",
    dot: "bg-purple-500",
  },
  running: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-500" },
  paused: {
    bg: "bg-yellow-50",
    text: "text-yellow-700",
    dot: "bg-yellow-500",
  },
  completed: {
    bg: "bg-green-50",
    text: "text-green-700",
    dot: "bg-green-500",
  },
  cancelled: { bg: "bg-gray-50", text: "text-gray-600", dot: "bg-gray-400" },
  failed: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
};

export function getCampaignStatusColor(status: CampaignStatus) {
  return CAMPAIGN_STATUS_COLORS[status] ?? CAMPAIGN_STATUS_COLORS.draft;
}

const CONTACT_STATUS_COLORS: Record<
  CampaignContactStatus,
  { bg: string; text: string; dot: string }
> = {
  pending: { bg: "bg-gray-100", text: "text-gray-700", dot: "bg-gray-400" },
  queued: { bg: "bg-blue-50", text: "text-blue-700", dot: "bg-blue-400" },
  calling: { bg: "bg-indigo-50", text: "text-indigo-700", dot: "bg-indigo-500" },
  completed: { bg: "bg-green-50", text: "text-green-700", dot: "bg-green-500" },
  failed: { bg: "bg-red-50", text: "text-red-700", dot: "bg-red-500" },
  retry_scheduled: {
    bg: "bg-orange-50",
    text: "text-orange-700",
    dot: "bg-orange-400",
  },
  skipped: { bg: "bg-gray-50", text: "text-gray-500", dot: "bg-gray-300" },
  cancelled: { bg: "bg-gray-50", text: "text-gray-600", dot: "bg-gray-400" },
  no_answer: { bg: "bg-yellow-50", text: "text-yellow-700", dot: "bg-yellow-400" },
  busy: { bg: "bg-amber-50", text: "text-amber-700", dot: "bg-amber-400" },
  voicemail: { bg: "bg-purple-50", text: "text-purple-700", dot: "bg-purple-400" },
  do_not_call: { bg: "bg-red-50", text: "text-red-600", dot: "bg-red-400" },
};

export function getContactStatusColor(status: CampaignContactStatus) {
  return CONTACT_STATUS_COLORS[status] ?? CONTACT_STATUS_COLORS.pending;
}

const WRITEBACK_STATUS_COLORS: Record<
  WritebackStatus,
  { bg: string; text: string }
> = {
  pending: { bg: "bg-gray-100", text: "text-gray-700" },
  success: { bg: "bg-green-50", text: "text-green-700" },
  failed: { bg: "bg-red-50", text: "text-red-700" },
  skipped: { bg: "bg-gray-50", text: "text-gray-500" },
};

export function getWritebackStatusColor(status: WritebackStatus) {
  return WRITEBACK_STATUS_COLORS[status] ?? WRITEBACK_STATUS_COLORS.pending;
}

// ─── Display Labels ──────────────────────────────────────────────────────────

const CAMPAIGN_STATUS_LABELS: Record<CampaignStatus, string> = {
  draft: "Draft",
  loading_contacts: "Loading Contacts",
  ready: "Ready",
  scheduled: "Scheduled",
  running: "Running",
  paused: "Paused",
  completed: "Completed",
  cancelled: "Cancelled",
  failed: "Failed",
};

export function getCampaignStatusLabel(status: CampaignStatus): string {
  return CAMPAIGN_STATUS_LABELS[status] ?? status;
}

const CONTACT_STATUS_LABELS: Record<CampaignContactStatus, string> = {
  pending: "Pending",
  queued: "Queued",
  calling: "Calling",
  completed: "Completed",
  failed: "Failed",
  retry_scheduled: "Retry Scheduled",
  skipped: "Skipped",
  cancelled: "Cancelled",
  no_answer: "No Answer",
  busy: "Busy",
  voicemail: "Voicemail",
  do_not_call: "Do Not Call",
};

export function getContactStatusLabel(status: CampaignContactStatus): string {
  return CONTACT_STATUS_LABELS[status] ?? status;
}

// ─── Formatting Helpers ──────────────────────────────────────────────────────

export function formatProgress(completed: number, total: number): string {
  if (total === 0) return "0%";
  return `${Math.round((completed / total) * 100)}%`;
}

export function getProgressPercent(completed: number, total: number): number {
  if (total === 0) return 0;
  return Math.round((completed / total) * 100);
}

export function formatPhoneNumber(phone: string): string {
  // Simple formatting: +1234567890 → +1 (234) 567-890
  if (phone.startsWith("+1") && phone.length === 12) {
    return `+1 (${phone.slice(2, 5)}) ${phone.slice(5, 8)}-${phone.slice(8)}`;
  }
  return phone;
}

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

// ─── CSV Export ───────────────────────────────────────────────────────────────

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
