import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

interface ChatInputProps {
  onSendMessage: (message: string) => Promise<void>;
  isSending: boolean;
}

export function ChatInput({ onSendMessage, isSending }: ChatInputProps): JSX.Element {
  const [message, setMessage] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async () => {
    const clean = message.trim();
    if (!clean || isSending) {
      return;
    }

    setMessage("");
    await onSendMessage(clean);
    inputRef.current?.focus();
  };

  const handleKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await handleSend();
    }
  };

  return (
    <div className="border-t border-slate-700/80 bg-slate-900/70 px-4 py-4 sm:px-6">
      <div className="flex items-end gap-3">
        <textarea
          ref={inputRef}
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your message..."
          rows={1}
          className="max-h-36 min-h-[48px] flex-1 resize-y rounded-xl border border-slate-700 bg-slate-950/70 px-4 py-3 font-body text-sm text-slate-100 outline-none transition focus:border-cyan-400/70 focus:ring-2 focus:ring-cyan-400/20"
        />
        <motion.button
          type="button"
          whileHover={{ scale: isSending ? 1 : 1.03 }}
          whileTap={{ scale: isSending ? 1 : 0.97 }}
          onClick={handleSend}
          disabled={isSending || message.trim().length === 0}
          className="h-12 rounded-xl bg-cyan-500 px-5 font-display text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/25 transition disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400 disabled:shadow-none"
        >
          {isSending ? "Sending..." : "Send"}
        </motion.button>
      </div>
    </div>
  );
}
