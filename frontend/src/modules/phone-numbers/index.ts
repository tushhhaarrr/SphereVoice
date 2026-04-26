/**
 * Phone Numbers Module — Public API
 */

// Components
export { PhoneNumbersTable } from "./components/phone-numbers-table";
export { SearchNumbersDialog } from "./components/search-numbers-dialog";
export { AssignAgentDialog } from "./components/assign-agent-dialog";

// Hooks
export {
  usePhoneNumbers,
  useSearchAvailableNumbers,
  usePurchaseNumber,
  useAssignAgent,
  useReleaseNumber,
  useSyncPlivoNumbers,
  useSetDefaultOutbound,
  useClearDefaultOutbound,
} from "./hooks/use-phone-numbers";

// Types
export type {
  PhoneNumber,
  AvailableNumber,
  PhoneNumberCapabilities,
  PhoneNumberListResponse,
  PhoneNumberSearchResponse,
  PhoneNumberListParams,
  PhoneNumberSearchParams,
  PhoneNumberPurchaseRequest,
  PhoneNumberAssignRequest,
} from "./types";
