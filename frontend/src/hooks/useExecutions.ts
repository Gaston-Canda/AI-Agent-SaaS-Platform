import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  executeAgent,
  executeAgentAsync,
  executeAgentStreaming,
  getExecutionDetail,
  getExecutionHistory,
  type StreamHandlers,
} from "../api/executions";

const ACTIVE_STATUS = new Set(["pending", "running", "queued"]);

export function useExecutionHistory(agentId: string, params: { skip?: number; limit?: number } = {}) {
  return useQuery({
    queryKey: ["executions", "history", agentId, params.skip ?? 0, params.limit ?? 200],
    queryFn: () => getExecutionHistory(agentId, params),
    enabled: Boolean(agentId),
    refetchInterval: (query) => {
      const rows = query.state.data ?? [];
      const hasActive = rows.some((row) => ACTIVE_STATUS.has(String(row.status).toLowerCase()));
      return hasActive ? 3000 : false;
    },
  });
}

export function useExecutionDetail(agentId: string, executionId: string | null) {
  return useQuery({
    queryKey: ["executions", "detail", agentId, executionId],
    queryFn: () => getExecutionDetail(agentId, executionId as string),
    enabled: Boolean(agentId && executionId),
    refetchInterval: (query) => {
      const status = String(query.state.data?.status ?? "").toLowerCase();
      return ACTIVE_STATUS.has(status) ? 2000 : false;
    },
  });
}

export function useExecuteSync(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => executeAgent(agentId, message),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ["executions", "history", agentId] });
      await queryClient.invalidateQueries({
        queryKey: ["executions", "detail", agentId, data.execution_id],
      });
    },
  });
}

interface ExecuteStreamInput {
  message: string;
  handlers?: StreamHandlers;
}

export function useExecuteSyncStreaming(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: ExecuteStreamInput) =>
      executeAgentStreaming(agentId, input.message, input.handlers),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ["executions", "history", agentId] });
      await queryClient.invalidateQueries({
        queryKey: ["executions", "detail", agentId, data.execution_id],
      });
    },
  });
}

export function useExecuteAsync(agentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (message: string) => executeAgentAsync(agentId, message),
    onSuccess: async (data) => {
      await queryClient.invalidateQueries({ queryKey: ["executions", "history", agentId] });
      await queryClient.invalidateQueries({
        queryKey: ["executions", "detail", agentId, data.execution_id],
      });
    },
  });
}
