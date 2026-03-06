interface MemoryMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
}

interface MemoryViewerProps {
  systemPrompt: string;
  messages: MemoryMessage[];
}

export function MemoryViewer({ systemPrompt, messages }: MemoryViewerProps): JSX.Element {
  return (
    <div className="space-y-3">
      <section className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
        <h4 className="text-xs font-semibold text-slate-200">System Prompt</h4>
        <p className="mt-1 whitespace-pre-wrap text-xs text-slate-300">{systemPrompt || "Not available"}</p>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
        <h4 className="text-xs font-semibold text-slate-200">Conversation Context</h4>
        <div className="mt-2 max-h-64 space-y-2 overflow-auto">
          {messages.map((message) => (
            <div key={message.id} className="rounded border border-slate-800 p-2">
              <p className="text-[10px] uppercase text-slate-500">{message.role}</p>
              <p className="mt-1 whitespace-pre-wrap text-xs text-slate-300">{message.content}</p>
            </div>
          ))}
          {messages.length === 0 ? <p className="text-xs text-slate-500">No memory context yet.</p> : null}
        </div>
      </section>
    </div>
  );
}

export type { MemoryMessage };
