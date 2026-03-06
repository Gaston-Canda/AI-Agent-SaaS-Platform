import type { ExecutionDetail } from "../api/executions";

interface CostTrackerProps {
  execution: ExecutionDetail | null;
}

const COST_PER_1K_TOKENS = 0.002;

export function CostTracker({ execution }: CostTrackerProps): JSX.Element {
  if (!execution) {
    return <p className="text-xs text-slate-500">Select an execution to view usage metrics.</p>;
  }

  const promptTokens = execution.logs.reduce((total, row) => total + (row.prompt_tokens ?? 0), 0);
  const completionTokens = execution.logs.reduce((total, row) => total + (row.completion_tokens ?? 0), 0);
  const totalTokens =
    (execution.output_data?.tokens_used as number | undefined) ?? promptTokens + completionTokens;
  const llmLatency = execution.logs.reduce((total, row) => total + (row.llm_latency_ms ?? 0), 0);
  const toolLatency = execution.logs.reduce((total, row) => total + (row.tool_latency_ms ?? 0), 0);
  const executionTime = execution.execution_time_ms ?? 0;
  const estimatedCost = (totalTokens / 1000) * COST_PER_1K_TOKENS;

  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <MetricCard label="Total Tokens" value={String(totalTokens)} />
      <MetricCard label="Prompt Tokens" value={String(promptTokens)} />
      <MetricCard label="Completion Tokens" value={String(completionTokens)} />
      <MetricCard label="Execution Time" value={`${executionTime} ms`} />
      <MetricCard label="LLM Latency" value={`${llmLatency} ms`} />
      <MetricCard label="Tool Latency" value={`${toolLatency} ms`} />
      <MetricCard label="Estimated Cost" value={`$${estimatedCost.toFixed(4)}`} />
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <p className="text-[11px] uppercase text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-100">{value}</p>
    </div>
  );
}
