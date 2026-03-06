import { useExecutionDetail } from "../hooks/useExecutions";

interface ExecutionViewerProps {
  agentId: string;
  executionId: string | null;
}

export function ExecutionViewer({ agentId, executionId }: ExecutionViewerProps): JSX.Element {
  const { data, isLoading, error } = useExecutionDetail(agentId, executionId);

  if (!executionId) {
    return <p className="text-xs text-slate-500">Select an execution to inspect details.</p>;
  }
  if (isLoading) {
    return <p className="text-xs text-slate-400">Loading execution...</p>;
  }
  if (error) {
    return <p className="text-xs text-rose-400">{(error as Error).message}</p>;
  }
  if (!data) {
    return <p className="text-xs text-slate-500">Execution not found.</p>;
  }

  const response = data.output_data?.response;

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
        <p className="text-xs text-slate-300">Status: {data.status}</p>
        <p className="text-xs text-slate-400">Execution: {data.id}</p>
        <p className="text-xs text-slate-400">Time: {data.execution_time_ms ?? 0} ms</p>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
        <h4 className="mb-2 text-xs font-semibold text-slate-200">Response</h4>
        <p className="whitespace-pre-wrap text-sm text-slate-100">{String(response ?? data.error_message ?? "")}</p>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-3">
        <h4 className="mb-2 text-xs font-semibold text-slate-200">Execution Logs</h4>
        <div className="max-h-52 space-y-2 overflow-auto pr-1">
          {data.logs.map((log) => (
            <div key={log.id} className="rounded border border-slate-800 p-2">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium text-slate-300">
                  {log.step}. {log.action}
                </span>
                <span className="text-[10px] text-slate-500">
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <pre className="mt-1 overflow-auto text-[10px] text-slate-400">
                {JSON.stringify(log.details, null, 2)}
              </pre>
            </div>
          ))}
          {data.logs.length === 0 ? <p className="text-xs text-slate-500">No logs recorded.</p> : null}
        </div>
      </div>
    </div>
  );
}
