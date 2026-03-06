import { apiClient } from "./client";

export interface Agent {
  id: string;
  tenant_id: string;
  created_by: string;
  name: string;
  description: string | null;
  agent_type: string;
  system_prompt: string | null;
  model: string;
  config: Record<string, unknown>;
  version: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CreateAgentInput {
  name: string;
  description?: string;
  agent_type?: string;
}

export async function getAgents(): Promise<Agent[]> {
  const response = await apiClient.get<Agent[]>("/api/agents");
  return response.data;
}

export async function getAgent(agentId: string): Promise<Agent> {
  const response = await apiClient.get<Agent>(`/api/agents/${agentId}`);
  return response.data;
}

export async function createAgent(input: CreateAgentInput): Promise<Agent> {
  const response = await apiClient.post<Agent>("/api/agents", {
    name: input.name,
    description: input.description ?? "",
    agent_type: input.agent_type ?? "chat",
    system_prompt: "You are a helpful assistant.",
    model: "gpt-4o-mini",
    config: {},
  });
  return response.data;
}
