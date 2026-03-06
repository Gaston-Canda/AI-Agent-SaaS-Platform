import { apiClient } from "./client";

export interface ExecuteResponse {
  execution_id: string;
  response: string;
  tokens_used: number;
  execution_time_ms: number;
  tools_executed: string[];
  status: string;
}

export interface ExecuteAsyncResponse {
  execution_id: string;
  status: string;
}

export interface ExecutionHistoryItem {
  id: string;
  agent_id: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  execution_time_ms: number | null;
  llm_provider: string | null;
  tools_called: Array<Record<string, unknown>> | null;
}

export interface ExecutionLog {
  id: string;
  execution_id: string;
  step: number;
  action: string;
  details: Record<string, unknown>;
  timestamp: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  cost_usd?: number;
  llm_provider?: string | null;
  tokens_used?: number;
  llm_latency_ms?: number;
  tool_latency_ms?: number;
  total_execution_time_ms?: number;
}

export interface ExecutionDetail {
  id: string;
  agent_id: string;
  status: string;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  execution_time_ms: number | null;
  created_at: string;
  completed_at: string | null;
  logs: ExecutionLog[];
}

export interface HistoryQueryParams {
  skip?: number;
  limit?: number;
}

export interface StreamHandlers {
  onStart?: () => void;
  onToken?: (token: string, aggregate: string) => void;
  onComplete?: (result: ExecuteResponse) => void;
}

export async function executeAgent(agentId: string, message: string): Promise<ExecuteResponse> {
  const response = await apiClient.post<ExecuteResponse>(`/api/agents/${agentId}/execute`, { message });
  return response.data;
}

export async function executeAgentAsync(agentId: string, message: string): Promise<ExecuteAsyncResponse> {
  const response = await apiClient.post<ExecuteAsyncResponse>(`/api/agents/${agentId}/execute-async`, { message });
  return response.data;
}

export async function getExecutionHistory(
  agentId: string,
  params: HistoryQueryParams = {}
): Promise<ExecutionHistoryItem[]> {
  const response = await apiClient.get<ExecutionHistoryItem[]>(`/api/agents/${agentId}/executions`, {
    params: {
      skip: params.skip ?? 0,
      limit: params.limit ?? 200,
    },
  });
  return response.data;
}

export async function getExecutionDetail(agentId: string, executionId: string): Promise<ExecutionDetail> {
  const response = await apiClient.get<ExecutionDetail>(`/api/agents/${agentId}/executions/${executionId}`);
  return response.data;
}

export async function executeAgentStreaming(
  agentId: string,
  message: string,
  handlers: StreamHandlers = {}
): Promise<ExecuteResponse> {
  handlers.onStart?.();

  const result = await executeAgent(agentId, message);

  // Future-ready streaming adapter:
  // when backend supports native streaming, replace this simulation layer
  // with SSE/WebSocket/chunked transfer consumption.
  const words = result.response.split(/\s+/).filter(Boolean);
  let aggregate = "";
  for (let index = 0; index < words.length; index += 1) {
    const token = words[index];
    aggregate = index === 0 ? token : `${aggregate} ${token}`;
    handlers.onToken?.(token, aggregate);
    // Minimal delay to render progressive updates in current non-streaming backend.
    // eslint-disable-next-line no-await-in-loop
    await new Promise((resolve) => setTimeout(resolve, 20));
  }

  handlers.onComplete?.(result);
  return result;
}
