import { useState } from "react";
import { Navbar } from "../components/Navbar";
import { AgentCard } from "../components/AgentCard";
import { useAgents, useCreateAgent } from "../hooks/useAgents";

export function DashboardPage(): JSX.Element {
  const { data, isLoading, error } = useAgents();
  const createMutation = useCreateAgent();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  const submit = async (): Promise<void> => {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    await createMutation.mutateAsync({ name: trimmed, description });
    setName("");
    setDescription("");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Navbar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <section className="mb-6 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h1 className="text-sm font-semibold text-slate-100">Create Agent</h1>
          <div className="mt-3 grid gap-2 md:grid-cols-[1fr_2fr_auto]">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="Agent name"
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <input
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="Description"
              className="rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm"
            />
            <button
              type="button"
              onClick={() => void submit()}
              disabled={createMutation.isPending}
              className="rounded-md bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-500 disabled:bg-slate-700"
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </button>
          </div>
          {createMutation.error ? (
            <p className="mt-2 text-xs text-rose-400">{(createMutation.error as Error).message}</p>
          ) : null}
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-100">Agents</h2>
          {isLoading ? <p className="text-sm text-slate-400">Loading agents...</p> : null}
          {error ? <p className="text-sm text-rose-400">{(error as Error).message}</p> : null}
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            {data?.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        </section>
      </main>
    </div>
  );
}
