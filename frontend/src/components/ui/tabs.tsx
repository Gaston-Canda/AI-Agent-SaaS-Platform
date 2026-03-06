import * as React from "react";
import { cn } from "../../lib/utils";
import { Button } from "./button";

interface TabsContextValue {
  value: string;
  onValueChange: (value: string) => void;
}

const TabsContext = React.createContext<TabsContextValue | null>(null);

function useTabsContext(): TabsContextValue {
  const context = React.useContext(TabsContext);
  if (!context) {
    throw new Error("Tabs components must be used within Tabs");
  }
  return context;
}

function Tabs({
  value,
  onValueChange,
  className,
  children,
}: React.PropsWithChildren<{ value: string; onValueChange: (value: string) => void; className?: string }>) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={cn("w-full", className)}>{children}</div>
    </TabsContext.Provider>
  );
}

function TabsList({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("inline-flex rounded-md border border-slate-700 p-0.5", className)} {...props} />;
}

function TabsTrigger({
  value,
  className,
  children,
}: React.PropsWithChildren<{ value: string; className?: string }>) {
  const context = useTabsContext();
  const active = context.value === value;
  return (
    <Button
      type="button"
      size="sm"
      variant={active ? "default" : "ghost"}
      onClick={() => context.onValueChange(value)}
      className={cn("capitalize", active ? "bg-slate-700 hover:bg-slate-700" : "text-slate-400", className)}
    >
      {children}
    </Button>
  );
}

function TabsContent({
  value,
  className,
  children,
}: React.PropsWithChildren<{ value: string; className?: string }>) {
  const context = useTabsContext();
  if (context.value !== value) {
    return null;
  }
  return <div className={cn("mt-3", className)}>{children}</div>;
}

export { Tabs, TabsList, TabsTrigger, TabsContent };
