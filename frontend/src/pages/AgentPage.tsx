import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AgentLogsPanel } from "../components/AgentLogsPanel";
import { ChatConsole, type ChatMessage } from "../components/ChatConsole";
import { CostTracker } from "../components/CostTracker";
import { ExecutionHistoryTable } from "../components/ExecutionHistoryTable";
import { MemoryViewer } from "../components/MemoryViewer";
import { Navbar } from "../components/Navbar";
import { ToolExecutionViewer, type ToolExecutionItem } from "../components/ToolExecutionViewer";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { useAgent } from "../hooks/useAgents";
import { useExecutionDetail, useExecutionHistory } from "../hooks/useExecutions";

type AgentTab = "executions" | "logs" | "memory" | "tools" | "cost";

export function AgentPage(): JSX.Element {
  const params = useParams<{ agentId: string }>();
  const agentId = params.agentId ?? "";
  const [activeTab, setActiveTab] = useState<AgentTab>("executions");
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ChatMessage[]>([]);

  const agentQuery = useAgent(agentId);
  const historyQuery = useExecutionHistory(agentId, { skip: 0, limit: 200 });
  const detailQuery = useExecutionDetail(agentId, selectedExecutionId);
  const executionDetail = detailQuery.data ?? null;

  const memoryMessages = useMemo(
    () =>
      conversation.map((message) => ({
        id: message.id,
        role: message.role,
        content: message.content,
      })),
    [conversation]
  );

  const toolItems = useMemo<ToolExecutionItem[]>(() => {
    if (!executionDetail) {
      return [];
    }

    return executionDetail.logs
      .filter((log) => log.action === "execute_tool")
      .map((log) => {
        const details = (log.details?.details as Record<string, unknown> | undefined) ?? {};
        return {
          id: log.id,
          toolName: String(details.tool_name ?? "unknown_tool"),
          status: log.details?.success === false ? "failed" : "completed",
          input: (details.tool_input as Record<string, unknown> | undefined) ?? null,
          output: details.result_preview ?? log.details,
          error: (log.details?.error as string | undefined) ?? null,
        };
      });
  }, [executionDetail]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950">
      <Navbar />
      <main className="mx-auto max-w-[94rem] px-4 py-6">
        <div className="mb-4">
          <Link to="/dashboard" className="text-xs text-sky-400 hover:text-sky-300">
            {"<- Back to dashboard"}
          </Link>
        </div>

        <Card className="mb-4">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">{agentQuery.data?.name ?? "Agent"}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-slate-400">{agentQuery.data?.description ?? "No description"}</p>
          </CardContent>
        </Card>

        <div className="grid gap-4 xl:grid-cols-[2.2fr_1.3fr]">
          <div>
            <ChatConsole
              agentId={agentId}
              onExecutionCreated={(executionId) => {
                setSelectedExecutionId(executionId);
                setActiveTab("executions");
                void historyQuery.refetch();
              }}
              onConversationUpdate={setConversation}
            />
          </div>

          <Card>
            <CardContent className="pt-4">
              <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as AgentTab)}>
                <TabsList>
                  <TabsTrigger value="executions">Executions</TabsTrigger>
                  <TabsTrigger value="logs">Logs</TabsTrigger>
                  <TabsTrigger value="tools">Tools</TabsTrigger>
                  <TabsTrigger value="memory">Memory</TabsTrigger>
                  <TabsTrigger value="cost">Cost</TabsTrigger>
                </TabsList>

                <TabsContent value="executions">
                  <ExecutionHistoryTable
                    items={historyQuery.data ?? []}
                    selectedExecutionId={selectedExecutionId}
                    onSelectExecution={setSelectedExecutionId}
                  />
                </TabsContent>

                <TabsContent value="logs">
                  <AgentLogsPanel logs={executionDetail?.logs ?? []} />
                </TabsContent>

                <TabsContent value="memory">
                  <MemoryViewer
                    systemPrompt={agentQuery.data?.system_prompt ?? ""}
                    messages={memoryMessages}
                  />
                </TabsContent>

                <TabsContent value="tools">
                  <ToolExecutionViewer items={toolItems} />
                </TabsContent>

                <TabsContent value="cost">
                  <CostTracker execution={executionDetail} />
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
