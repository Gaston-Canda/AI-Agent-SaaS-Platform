import { apiClient } from "./client";

export interface AuthUser {
  id: string;
  tenant_id: string;
  email: string;
  username: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: AuthUser;
}

export interface LoginInput {
  tenantSlug: string;
  email: string;
  password: string;
}

export interface RegisterInput {
  tenantSlug: string;
  email: string;
  username: string;
  password: string;
}

export async function login(input: LoginInput): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>(
    `/api/auth/login?tenant_slug=${encodeURIComponent(input.tenantSlug)}`,
    {
      email: input.email,
      password: input.password,
    }
  );
  return response.data;
}

export async function register(input: RegisterInput): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>(
    `/api/auth/register?tenant_slug=${encodeURIComponent(input.tenantSlug)}`,
    {
      email: input.email,
      username: input.username,
      password: input.password,
    }
  );
  return response.data;
}
