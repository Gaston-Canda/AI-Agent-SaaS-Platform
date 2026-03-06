import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AgentHeader } from "../components/AgentHeader";
import { ChatInput } from "../components/ChatInput";
import { ChatWindow } from "../components/ChatWindow";
import { ChatMessage } from "../components/MessageBubble";
import { executeAgent } from "../services/api";
import { theme } from "../styles/theme";

function createMessage(partial: Omit<ChatMessage, "id" | "createdAt">): ChatMessage {
  return {
    id: crypto.randomUUID(),
    createdAt: new Date().toISOString(),
    ...partial
  };
}

const AGENT_ID = import.meta.env.VITE_AGENT_ID ?? "replace-with-agent-id";
const AGENT_NAME = import.meta.env.VITE_AGENT_NAME ?? theme.defaultAgentName;
const ACCESS_TOKEN = import.meta.env.VITE_ACCESS_TOKEN;

export function AgentConsole(): JSX.Element {
  const [messages, setMessages] = useState<ChatMessage[]>([
    createMessage({
      role: "agent",
      content:
        "Welcome. I am ready to help you. Send a message and I will execute the configured backend agent."
    })
  ]);
  const [isThinking, setIsThinking] = useState(false);

  const isConfigured = useMemo(() => AGENT_ID !== "replace-with-agent-id", []);

  const handleSendMessage = async (message: string) => {
    if (isThinking) {
      return;
    }

    setMessages((current) =>
      current.concat(
        createMessage({
          role: "user",
          content: message
        })
      )
    );

    setIsThinking(true);

    try {
      if (!isConfigured) {
        throw new Error("Set VITE_AGENT_ID in your frontend environment before sending messages.");
      }

      const result = await executeAgent(AGENT_ID, message, ACCESS_TOKEN);

      setMessages((current) =>
        current.concat(
          createMessage({
            role: "agent",
            content: result.response,
            metadata: {
              executionId: result.execution_id,
              tokensUsed: result.tokens_used,
              executionTimeMs: result.execution_time_ms,
              toolsExecuted: result.tools_executed
            }
          })
        )
      );
    } catch (error) {
      const errorMessage =
        error instanceof Error ? error.message : "Unknown error while executing the agent.";

      setMessages((current) =>
        current.concat(
          createMessage({
            role: "error",
            content: `Execution error: ${errorMessage}`
          })
        )
      );
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className={`min-h-screen ${theme.colors.background} px-3 py-4 sm:px-6 sm:py-8`}>
      <div className="mx-auto w-full max-w-5xl">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: "easeOut" }}
          className={`overflow-hidden rounded-2xl ${theme.colors.surface} shadow-xl backdrop-blur`}
        >
          <AgentHeader agentName={AGENT_NAME} agentId={AGENT_ID} isOnline={true} />
          <ChatWindow messages={messages} isThinking={isThinking} />
          <ChatInput onSendMessage={handleSendMessage} isSending={isThinking} />
        </motion.div>
      </div>
    </div>
  );
}
