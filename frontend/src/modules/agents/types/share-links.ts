/**
 * Share Link types — mirrors backend share_link_schemas.py
 */

export type ExpiryPreset = "15m" | "1h" | "24h" | "7d" | "30d" | "never";

export interface ShareLink {
  id: string;
  agent_id: string;
  token: string;
  label: string | null;
  expires_at: string | null;
  max_uses: number | null;
  use_count: number;
  is_active: boolean;
  created_at: string;
}

export interface ShareLinkListResponse {
  links: ShareLink[];
}

export interface ShareLinkCreateRequest {
  label?: string | null;
  expiry: ExpiryPreset;
  max_uses?: number | null;
}
