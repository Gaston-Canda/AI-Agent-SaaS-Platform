import { motion } from "framer-motion";

interface StreamingMessageProps {
  content: string;
  isStreaming: boolean;
  role?: "agent" | "system";
}

export function StreamingMessage({
  content,
  isStreaming,
  role = "agent",
}: StreamingMessageProps): JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-lg px-3 py-2 text-sm ${
        role === "system" ? "bg-amber-500/10 text-amber-200" : "bg-slate-900 text-slate-100"
      }`}
    >
      <p className="whitespace-pre-wrap">
        {content}
        {isStreaming ? (
          <motion.span
            animate={{ opacity: [0.2, 1, 0.2] }}
            transition={{ duration: 1, repeat: Infinity, ease: "easeInOut" }}
            className="ml-1 inline-block"
          >
            ...
          </motion.span>
        ) : null}
      </p>
    </motion.div>
  );
}
