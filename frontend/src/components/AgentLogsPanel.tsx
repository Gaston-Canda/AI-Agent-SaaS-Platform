import type { ExecutionLog } from "../api/executions";

interface AgentLogsPanelProps {
  logs: ExecutionLog[];
}

export function AgentLogsPanel({ logs }: AgentLogsPanelProps): JSX.Element {
  if (logs.length === 0) {
    return <p className="text-xs text-slate-500">No logs available.</p>;
  }

  return (
    <div className="max-h-[28rem] space-y-2 overflow-auto rounded-lg border border-slate-800 bg-[#0a0f1a] p-3 font-mono">
      {logs.map((log) => (
        <div key={log.id} className="rounded border border-slate-800 bg-slate-950/60 p-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] text-sky-300">
              {log.step}. {log.action}
            </span>
            <span className="text-[10px] text-slate-500">{new Date(log.timestamp).toLocaleTimeString()}</span>
          </div>
          <pre className="mt-1 overflow-auto text-[10px] text-slate-300">{JSON.stringify(log.details, null, 2)}</pre>
        </div>
      ))}
    </div>
  );
}
