import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createAgent, getAgent, getAgents, type CreateAgentInput } from "../api/agents";

export function useAgents() {
  return useQuery({
    queryKey: ["agents"],
    queryFn: getAgents,
  });
}

export function useAgent(agentId: string) {
  return useQuery({
    queryKey: ["agents", agentId],
    queryFn: () => getAgent(agentId),
    enabled: Boolean(agentId),
  });
}

export function useCreateAgent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateAgentInput) => createAgent(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["agents"] });
    },
  });
}
