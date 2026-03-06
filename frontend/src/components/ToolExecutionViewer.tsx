interface ToolExecutionItem {
  id: string;
  toolName: string;
  status: "pending" | "running" | "completed" | "failed";
  input?: Record<string, unknown> | null;
  output?: unknown;
  error?: string | null;
}

interface ToolExecutionViewerProps {
  items: ToolExecutionItem[];
}

function statusClass(status: ToolExecutionItem["status"]): string {
  if (status === "completed") {
    return "bg-emerald-500/20 text-emerald-300";
  }
  if (status === "failed") {
    return "bg-rose-500/20 text-rose-300";
  }
  if (status === "running") {
    return "bg-sky-500/20 text-sky-300";
  }
  return "bg-amber-500/20 text-amber-300";
}

export function ToolExecutionViewer({ items }: ToolExecutionViewerProps): JSX.Element {
  if (items.length === 0) {
    return <p className="text-xs text-slate-500">No tool activity for this execution.</p>;
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-slate-200">{item.toolName}</h4>
            <span className={`rounded-full px-2 py-0.5 text-[10px] ${statusClass(item.status)}`}>
              {item.status}
            </span>
          </div>

          {item.input ? (
            <div className="mt-2">
              <p className="text-[10px] uppercase text-slate-500">input</p>
              <pre className="mt-1 overflow-auto text-[11px] text-slate-300">
                {JSON.stringify(item.input, null, 2)}
              </pre>
            </div>
          ) : null}

          <div className="mt-2">
            <p className="text-[10px] uppercase text-slate-500">output</p>
            <pre className="mt-1 overflow-auto text-[11px] text-slate-300">
              {item.error ? item.error : JSON.stringify(item.output, null, 2)}
            </pre>
          </div>
        </div>
      ))}
    </div>
  );
}

export type { ToolExecutionItem };
