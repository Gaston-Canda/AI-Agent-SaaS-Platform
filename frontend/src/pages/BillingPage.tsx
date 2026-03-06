import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  cancelSubscription,
  createCheckout,
  getBillingPlans,
  getBillingSubscription,
  getBillingUsage,
} from "../api/billing";
import { Navbar } from "../components/Navbar";

function ProgressBar({ value, limit }: { value: number; limit: number }): JSX.Element {
  const pct = limit > 0 ? Math.min(100, Math.round((value / limit) * 100)) : 0;
  return (
    <div className="mt-1 h-2 w-full rounded bg-slate-800">
      <div className="h-2 rounded bg-sky-500" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function BillingPage(): JSX.Element {
  const queryClient = useQueryClient();
  const plansQuery = useQuery({ queryKey: ["billing", "plans"], queryFn: getBillingPlans });
  const subscriptionQuery = useQuery({
    queryKey: ["billing", "subscription"],
    queryFn: getBillingSubscription,
  });
  const usageQuery = useQuery({ queryKey: ["billing", "usage"], queryFn: getBillingUsage });

  const checkoutMutation = useMutation({
    mutationFn: (planName: string) => createCheckout(planName),
    onSuccess: (result) => {
      if (result.checkout_url) {
        window.location.href = result.checkout_url;
      }
      void queryClient.invalidateQueries({ queryKey: ["billing"] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: cancelSubscription,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["billing"] });
    },
  });

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <Navbar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <h1 className="text-lg font-semibold">Billing & Subscription</h1>

        <section className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h2 className="text-sm font-semibold">Current Plan</h2>
          {subscriptionQuery.isLoading ? <p className="mt-2 text-sm text-slate-400">Loading...</p> : null}
          {subscriptionQuery.data ? (
            <div className="mt-3 grid gap-2 text-sm text-slate-300 md:grid-cols-3">
              <p>Plan: <span className="font-semibold text-slate-100">{subscriptionQuery.data.plan_name}</span></p>
              <p>Status: <span className="font-semibold text-slate-100">{subscriptionQuery.data.status}</span></p>
              <p>Trial: <span className="font-semibold text-slate-100">{subscriptionQuery.data.trial_active ? "Active" : "Inactive"}</span></p>
            </div>
          ) : null}
          <div className="mt-3">
            <button
              type="button"
              onClick={() => void cancelMutation.mutateAsync()}
              disabled={cancelMutation.isPending}
              className="rounded-md border border-rose-500/60 px-3 py-1.5 text-xs text-rose-300 hover:bg-rose-500/10 disabled:opacity-60"
            >
              {cancelMutation.isPending ? "Cancelling..." : "Cancel At Period End"}
            </button>
          </div>
        </section>

        <section className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h2 className="text-sm font-semibold">Usage Dashboard (Monthly)</h2>
          {usageQuery.data ? (
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
                <p className="text-xs text-slate-400">Tokens</p>
                <p className="text-sm">{usageQuery.data.tokens_used} / {usageQuery.data.tokens_limit}</p>
                <ProgressBar value={usageQuery.data.tokens_used} limit={usageQuery.data.tokens_limit} />
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
                <p className="text-xs text-slate-400">Executions</p>
                <p className="text-sm">{usageQuery.data.executions_used} / {usageQuery.data.executions_limit}</p>
                <ProgressBar value={usageQuery.data.executions_used} limit={usageQuery.data.executions_limit} />
              </div>
              <div className="rounded-md border border-slate-800 bg-slate-950/60 p-3">
                <p className="text-xs text-slate-400">Tool Calls</p>
                <p className="text-sm">{usageQuery.data.tools_used} / {usageQuery.data.tools_limit}</p>
                <ProgressBar value={usageQuery.data.tools_used} limit={usageQuery.data.tools_limit} />
              </div>
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-400">Loading usage...</p>
          )}
        </section>

        <section className="mt-4 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
          <h2 className="text-sm font-semibold">Upgrade Options</h2>
          {plansQuery.data ? (
            <div className="mt-3 grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              {plansQuery.data.map((plan) => (
                <div key={plan.id} className="rounded-lg border border-slate-800 bg-slate-950/50 p-3">
                  <p className="text-sm font-semibold capitalize">{plan.plan_name}</p>
                  <p className="mt-1 text-xs text-slate-400">${plan.price}/{plan.billing_interval}</p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-300">
                    <li>Agents: {plan.max_agents}</li>
                    <li>Executions/mo: {plan.max_executions_month}</li>
                    <li>Tokens/mo: {plan.max_tokens_month}</li>
                    <li>Tool calls/mo: {plan.max_tool_calls}</li>
                  </ul>
                  <button
                    type="button"
                    onClick={() => void checkoutMutation.mutateAsync(plan.plan_name)}
                    disabled={checkoutMutation.isPending}
                    className="mt-3 w-full rounded-md bg-sky-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-500 disabled:opacity-60"
                  >
                    {checkoutMutation.isPending ? "Processing..." : "Choose Plan"}
                  </button>
                </div>
              ))}
            </div>
          ) : (
            <p className="mt-2 text-sm text-slate-400">Loading plans...</p>
          )}
        </section>
      </main>
    </div>
  );
}
