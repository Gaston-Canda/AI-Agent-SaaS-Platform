import { motion } from "framer-motion";

export function LoadingAnimation(): JSX.Element {
  return (
    <div className="flex items-center gap-2">
      {[0, 1, 2].map((index) => (
        <motion.span
          key={index}
          className="h-2 w-2 rounded-full bg-cyan-300"
          animate={{ y: [0, -5, 0], opacity: [0.35, 1, 0.35] }}
          transition={{
            duration: 0.9,
            repeat: Infinity,
            delay: index * 0.15,
            ease: "easeInOut"
          }}
        />
      ))}
    </div>
  );
}
