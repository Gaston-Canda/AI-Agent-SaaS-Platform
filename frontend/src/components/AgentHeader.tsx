import { motion } from "framer-motion";

interface AgentHeaderProps {
  agentName: string;
  agentId: string;
  isOnline: boolean;
}

export function AgentHeader({ agentName, agentId, isOnline }: AgentHeaderProps): JSX.Element {
  return (
    <div className="border-b border-slate-700/80 px-4 py-4 sm:px-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="font-display text-xl font-semibold text-slate-100">{agentName}</h1>
          <p className="mt-1 text-xs text-slate-400">Agent ID: {agentId}</p>
        </div>

        <div className="flex items-center gap-2">
          <motion.span
            animate={{ opacity: [0.45, 1, 0.45] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: "easeInOut" }}
            className={`h-2.5 w-2.5 rounded-full ${isOnline ? "bg-emerald-400 shadow-glow" : "bg-rose-400"}`}
          />
          <span className="text-sm font-medium text-slate-300">
            {isOnline ? "Agent Online" : "Agent Offline"}
          </span>
        </div>
      </div>
    </div>
  );
}
