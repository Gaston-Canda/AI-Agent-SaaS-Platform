import type { ExecutionHistoryItem } from "../api/executions";

interface ExecutionListProps {
  items: ExecutionHistoryItem[];
  selectedExecutionId: string | null;
  onSelect: (executionId: string) => void;
}

export function ExecutionList({
  items,
  selectedExecutionId,
  onSelect,
}: ExecutionListProps): JSX.Element {
  return (
    <div className="space-y-2">
      {items.map((item) => {
        const selected = item.id === selectedExecutionId;
        return (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={`w-full rounded-lg border px-3 py-2 text-left transition ${
              selected
                ? "border-sky-500 bg-sky-500/10"
                : "border-slate-800 bg-slate-900/70 hover:border-slate-600"
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-100">{item.status}</span>
              <span className="text-[11px] text-slate-500">
                {new Date(item.created_at).toLocaleTimeString()}
              </span>
            </div>
            <p className="mt-1 truncate text-[11px] text-slate-400">{item.id}</p>
          </button>
        );
      })}
      {items.length === 0 ? <p className="text-xs text-slate-500">No executions yet.</p> : null}
    </div>
  );
}
