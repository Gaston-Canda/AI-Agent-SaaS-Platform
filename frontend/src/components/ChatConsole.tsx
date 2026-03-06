import { useEffect, useMemo, useRef, useState } from "react";
import type { ExecuteResponse } from "../api/executions";
import { useExecuteAsync, useExecuteSyncStreaming } from "../hooks/useExecutions";
import { StreamingMessage } from "./StreamingMessage";
import { ToolExecutionViewer, type ToolExecutionItem } from "./ToolExecutionViewer";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "./ui/card";

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  meta?: string;
  isStreaming?: boolean;
  executionId?: string;
  tools?: ToolExecutionItem[];
}

interface ChatConsoleProps {
  agentId: string;
  onExecutionCreated: (executionId: string) => void;
  onConversationUpdate?: (messages: ChatMessage[]) => void;
}

export function ChatConsole({
  agentId,
  onExecutionCreated,
  onConversationUpdate,
}: ChatConsoleProps): JSX.Element {
  const [message, setMessage] = useState("");
  const [items, setItems] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<"sync" | "async">("sync");
  const syncMutation = useExecuteSyncStreaming(agentId);
  const asyncMutation = useExecuteAsync(agentId);
  const busy = syncMutation.isPending || asyncMutation.isPending;
  const streamMessageIdRef = useRef<string | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    onConversationUpdate?.(items);
  }, [items, onConversationUpdate]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    containerRef.current.scrollTop = containerRef.current.scrollHeight;
  }, [items]);

  const isTyping = useMemo(() => items.some((item) => item.isStreaming), [items]);

  const submit = async (): Promise<void> => {
    const trimmed = message.trim();
    if (!trimmed || busy) {
      return;
    }

    setItems((current) => [...current, { id: crypto.randomUUID(), role: "user", content: trimmed }]);
    setMessage("");

    try {
      if (mode === "sync") {
        await syncMutation.mutateAsync({
          message: trimmed,
          handlers: {
            onStart: () => {
              const streamId = crypto.randomUUID();
              streamMessageIdRef.current = streamId;
              setItems((current) => [
                ...current,
                {
                  id: streamId,
                  role: "agent",
                  content: "",
                  isStreaming: true,
                },
              ]);
            },
            onToken: (_token, aggregate) => {
              const streamId = streamMessageIdRef.current;
              if (!streamId) {
                return;
              }
              setItems((current) =>
                current.map((item) =>
                  item.id === streamId
                    ? {
                        ...item,
                        content: aggregate,
                      }
                    : item
                )
              );
            },
            onComplete: (response: ExecuteResponse) => {
              onExecutionCreated(response.execution_id);
              const tools: ToolExecutionItem[] = response.tools_executed.map((toolName, index) => ({
                id: `${response.execution_id}-${index}-${toolName}`,
                toolName,
                status: "completed",
                output: "Tool execution completed",
              }));

              const streamId = streamMessageIdRef.current;
              if (!streamId) {
                return;
              }
              setItems((current) =>
                current.map((item) =>
                  item.id === streamId
                    ? {
                        ...item,
                        isStreaming: false,
                        meta: `${response.tokens_used} tokens - ${response.execution_time_ms} ms`,
                        executionId: response.execution_id,
                        tools,
                      }
                    : item
                )
              );
              streamMessageIdRef.current = null;
            },
          },
        });
      } else {
        const response = await asyncMutation.mutateAsync(trimmed);
        onExecutionCreated(response.execution_id);
        setItems((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: "system",
            content: `Queued execution ${response.execution_id}`,
            executionId: response.execution_id,
          },
        ]);
      }
    } catch (error) {
      setItems((current) => [
        ...current,
        {
          id: crypto.randomUUID(),
          role: "system",
          content: (error as Error).message,
        },
      ]);
    }
  };

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle>Agent Console</CardTitle>
          <div className="rounded-md border border-slate-700 p-0.5 text-xs">
            <Button
              type="button"
              onClick={() => setMode("sync")}
              size="sm"
              variant={mode === "sync" ? "default" : "ghost"}
              className={mode === "sync" ? "bg-slate-700 hover:bg-slate-700" : ""}
            >
              Sync
            </Button>
            <Button
              type="button"
              onClick={() => setMode("async")}
              size="sm"
              variant={mode === "async" ? "default" : "ghost"}
              className={mode === "async" ? "bg-slate-700 hover:bg-slate-700" : ""}
            >
              Async
            </Button>
          </div>
        </div>

        <div className="flex items-center justify-between">
          <p className="text-[11px] text-slate-500">Mode: {mode.toUpperCase()}</p>
          {isTyping ? <Badge variant="running">running</Badge> : <Badge variant="completed">ready</Badge>}
        </div>
      </CardHeader>

      <CardContent>
        <div
          ref={containerRef}
          className="mb-3 h-80 space-y-2 overflow-auto rounded-lg border border-slate-800 bg-slate-950/60 p-3"
        >
          {items.map((item) => (
            <div key={item.id} className="space-y-1">
              <span className="text-[10px] uppercase text-slate-500">{item.role}</span>
              {item.role === "agent" || item.role === "system" ? (
                <StreamingMessage
                  content={item.content}
                  isStreaming={Boolean(item.isStreaming)}
                  role={item.role === "system" ? "system" : "agent"}
                />
              ) : (
                <div className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-slate-100">{item.content}</div>
              )}
              {item.meta ? <p className="text-[10px] text-slate-500">{item.meta}</p> : null}
              {item.tools && item.tools.length > 0 ? <ToolExecutionViewer items={item.tools} /> : null}
            </div>
          ))}
        </div>

        <div className="mb-2 flex items-center justify-between">
          <p className="text-[11px] text-slate-500">{isTyping ? "Agent is typing..." : "Ready"}</p>
        </div>

        <div className="flex gap-2">
          <input
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void submit();
              }
            }}
            placeholder="Write a message..."
            className="flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
          />
          <Button type="button" onClick={() => void submit()} disabled={busy}>
            {busy ? "Sending..." : "Send"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export type { ChatMessage };
