import { motion } from "framer-motion";
import { theme } from "../styles/theme";

export type MessageRole = "user" | "agent" | "error";

export interface MessageMetadata {
  executionId?: string;
  tokensUsed?: number;
  executionTimeMs?: number;
  toolsExecuted?: string[];
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  metadata?: MessageMetadata;
}

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps): JSX.Element {
  const isUser = message.role === "user";
  const isError = message.role === "error";

  const bubbleStyle = isError
    ? theme.colors.errorBubble
    : isUser
      ? theme.colors.userBubble
      : theme.colors.agentBubble;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut" }}
      className={`w-full ${isUser ? "flex justify-end" : "flex justify-start"}`}
    >
      <div className={`max-w-[85%] rounded-2xl px-4 py-3 shadow-xl ${bubbleStyle}`}>
        <p className="whitespace-pre-wrap text-[15px] leading-relaxed text-slate-100">
          {message.content}
        </p>

        {message.role === "agent" && message.metadata && (
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
            {typeof message.metadata.tokensUsed === "number" && (
              <span>Tokens: {message.metadata.tokensUsed}</span>
            )}
            {typeof message.metadata.executionTimeMs === "number" && (
              <span>Time: {message.metadata.executionTimeMs}ms</span>
            )}
            {message.metadata.toolsExecuted && message.metadata.toolsExecuted.length > 0 && (
              <span>Tools: {message.metadata.toolsExecuted.join(", ")}</span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}
