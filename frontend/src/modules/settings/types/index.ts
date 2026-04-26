/**
 * Settings module types.
 */

export interface WebhookConfig {
  id: string;
  url: string;
  events: string[];
  isActive: boolean;
}
