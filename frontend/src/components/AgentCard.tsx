import { Link } from "react-router-dom";
import type { Agent } from "../api/agents";

export function AgentCard({ agent }: { agent: Agent }): JSX.Element {
  return (
    <Link
      to={`/agents/${agent.id}`}
      className="block rounded-xl border border-slate-800 bg-slate-900/70 p-4 transition hover:border-slate-600"
    >
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-100">{agent.name}</h3>
        <span
          className={`rounded-full px-2 py-0.5 text-[10px] ${
            agent.is_active ? "bg-emerald-500/20 text-emerald-300" : "bg-slate-700 text-slate-300"
          }`}
        >
          {agent.is_active ? "active" : "inactive"}
        </span>
      </div>
      <p className="mt-2 line-clamp-2 text-xs text-slate-400">{agent.description || "No description"}</p>
      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-500">
        <span>Type: {agent.agent_type}</span>
        <span>v{agent.version}</span>
      </div>
    </Link>
  );
}
