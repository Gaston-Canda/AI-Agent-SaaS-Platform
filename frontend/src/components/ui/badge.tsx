import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva("inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium", {
  variants: {
    variant: {
      default: "bg-slate-700 text-slate-200",
      pending: "bg-amber-500/20 text-amber-300",
      running: "bg-sky-500/20 text-sky-300",
      completed: "bg-emerald-500/20 text-emerald-300",
      failed: "bg-rose-500/20 text-rose-300",
    },
  },
  defaultVariants: {
    variant: "default",
  },
});

function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
