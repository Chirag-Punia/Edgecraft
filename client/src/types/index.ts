export interface User {
  id: number;
  email: string;
  full_name: string;
  is_email_verified: boolean;
  auth_provider: "local" | "google";
  role: "owner" | "member";
  seller_id: number | null;
}

export interface Seller {
  id: number;
  business_name: string;
  business_type: string | null;
  primary_category: string | null;
  gst_number: string | null;
  city: string | null;
  state: string | null;
  onboarding_completed: boolean;
}

export interface MarketplaceAccount {
  id: number;
  seller_id: number;
  marketplace: "amazon" | "flipkart" | "shopify" | "facebook";
  status: "pending" | "connected" | "error" | "disconnected";
  last_sync_at: string | null;
  created_at: string;
}

export interface KPIData {
  title: string;
  value: string;
  change: string;
  change_type: "positive" | "negative" | "neutral";
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}
