import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { ChatMessage, MessageBubble } from "./MessageBubble";
import { LoadingAnimation } from "./LoadingAnimation";

interface ChatWindowProps {
  messages: ChatMessage[];
  isThinking: boolean;
}

export function ChatWindow({ messages, isThinking }: ChatWindowProps): JSX.Element {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isThinking]);

  return (
    <div className="h-[62vh] overflow-y-auto px-4 py-5 sm:px-6">
      <div className="space-y-4">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} />
        ))}

        {isThinking && (
          <motion.div
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start"
          >
            <div className="rounded-2xl border border-slate-700 bg-slate-800/80 px-4 py-3 shadow-xl">
              <LoadingAnimation />
            </div>
          </motion.div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}
