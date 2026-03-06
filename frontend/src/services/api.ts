import axios, { AxiosError } from "axios";

export interface ExecuteAgentResponse {
  execution_id: string;
  response: string;
  tokens_used: number;
  execution_time_ms: number;
  tools_executed: string[];
  status: string;
}

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
  timeout: 30000
});

export async function executeAgent(
  agentId: string,
  message: string,
  token?: string
): Promise<ExecuteAgentResponse> {
  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json"
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    const response = await apiClient.post<ExecuteAgentResponse>(
      `/api/agents/${agentId}/execute`,
      { message },
      { headers }
    );

    return response.data;
  } catch (error) {
    if (error instanceof AxiosError) {
      if (error.code === "ECONNABORTED") {
        throw new Error("The server took too long to respond.");
      }

      const apiError = error.response?.data?.detail;
      throw new Error(apiError || error.message || "Request failed.");
    }

    throw new Error("Unexpected error while executing the agent.");
  }
}
