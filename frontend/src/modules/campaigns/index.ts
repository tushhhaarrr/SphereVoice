/**
 * Campaigns Module — Public API
 */

// Components
export { CampaignList } from "./components/campaign-list";
export { CampaignWizard } from "./components/campaign-builder/campaign-wizard";
export { CampaignDashboard } from "./components/campaign-detail/campaign-dashboard";
export { CampaignStatsCards } from "./components/campaign-detail/campaign-stats-cards";
export { CampaignContactsTable } from "./components/campaign-detail/campaign-contacts-table";
export { ContactDetailDialog } from "./components/campaign-detail/contact-detail-dialog";

// Wizard Steps
export { StepAgentSelect } from "./components/campaign-builder/step-agent-select";
export { StepCrmSource } from "./components/campaign-builder/step-crm-source";
export { StepVariableMapping } from "./components/campaign-builder/step-variable-mapping";
export { StepWritebackMapping } from "./components/campaign-builder/step-writeback-mapping";
export { StepCallSettings } from "./components/campaign-builder/step-call-settings";
export { StepToolConfig } from "./components/campaign-builder/step-tool-config";
export { StepReview } from "./components/campaign-builder/step-review";

// Hooks
export {
    useCampaigns,
    useCampaign,
    useCampaignStats,
    useCampaignContacts,
    useCampaignContact,
    useCreateCampaign,
    useUpdateCampaign,
    useDeleteCampaign,
    useLoadContacts,
    useStartCampaign,
    usePauseCampaign,
    useResumeCampaign,
    useCancelCampaign,
    useRetryContact,
    useExportResults,
    campaignKeys,
} from "./hooks/use-campaigns";

// Utils
export {
    getCampaignStatusColor,
    getContactStatusColor,
    getWritebackStatusColor,
    getCampaignStatusLabel,
    getContactStatusLabel,
    formatProgress,
    getProgressPercent,
    formatPhoneNumber,
    formatDateTime,
    formatRelativeTime,
    downloadBlob,
} from "./lib/campaign-utils";

// Types
export type {
    CallingWindow,
    Campaign,
    CampaignContact,
    CampaignContactCreate,
    CampaignContactListItem,
    CampaignContactListParams,
    CampaignContactsListWrapper,
    CampaignCreate,
    CampaignListItem,
    CampaignListParams,
    CampaignsListWrapper,
    CampaignStats,
    CampaignUpdate,
    CampaignWizardData,
    LoadContactsRequest,
    LoadContactsResponse,
} from "./types";

export type { CampaignStatus, CampaignContactStatus, WritebackStatus } from "./types";
export { WIZARD_STEPS } from "./types";
export type { WizardStepKey } from "./types";
