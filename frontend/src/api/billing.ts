import { apiClient } from "./client";

export interface BillingPlan {
  id: string;
  plan_name: string;
  price: number;
  currency: string;
  billing_interval: string;
  max_agents: number;
  max_executions_month: number;
  max_tokens_month: number;
  max_tool_calls: number;
  concurrent_executions: number;
}

export interface BillingSubscription {
  id: string;
  tenant_id: string;
  plan_id: string | null;
  plan_name: string;
  status: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  trial_start: string | null;
  trial_end: string | null;
  trial_active: boolean;
}

export interface BillingUsage {
  plan_name: string;
  status: string;
  trial_active: boolean;
  trial_end: string | null;
  tokens_used: number;
  tokens_limit: number;
  executions_used: number;
  executions_limit: number;
  tools_used: number;
  tools_limit: number;
  max_agents: number;
}

export interface CheckoutResponse {
  session_id: string;
  checkout_url: string;
}

export async function getBillingPlans(): Promise<BillingPlan[]> {
  const response = await apiClient.get<BillingPlan[]>("/api/billing/plans");
  return response.data;
}

export async function getBillingSubscription(): Promise<BillingSubscription> {
  const response = await apiClient.get<BillingSubscription>("/api/billing/subscription");
  return response.data;
}

export async function getBillingUsage(): Promise<BillingUsage> {
  const response = await apiClient.get<BillingUsage>("/api/billing/usage");
  return response.data;
}

export async function createCheckout(planName: string): Promise<CheckoutResponse> {
  const response = await apiClient.post<CheckoutResponse>("/api/billing/checkout", {
    plan_name: planName,
  });
  return response.data;
}

export async function cancelSubscription(): Promise<{ status: string; cancel_at_period_end: boolean }> {
  const response = await apiClient.post<{ status: string; cancel_at_period_end: boolean }>("/api/billing/cancel");
  return response.data;
}
