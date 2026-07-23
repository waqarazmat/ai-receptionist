import { CheckCircle2, DollarSign, MessageSquare, Wallet, ArrowUpRight, Sparkles } from "lucide-react";
import { motion } from "framer-motion";
import { useOrgBilling } from "../../api/billing";
import { Card } from "../../components/ui/Card";
import { Skeleton } from "../../components/ui/Skeleton";
import { StatsCard } from "../../components/shared/StatsCard";
import { itemFadeLeft, staggerContainer } from "../../lib/motion";
import { Button } from "../../components/ui/Button";

const PLAN_ORDER = ["free", "starter", "pro", "enterprise"] as const;

const PLAN_TONE: Record<string, string> = {
  free: "bg-slate-100 text-slate-700 dark:bg-slate-700/50 dark:text-slate-200",
  starter: "bg-blue-50 text-blue-700 dark:bg-blue-500/10 dark:text-blue-300",
  pro: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300",
  enterprise:
    "bg-gradient-to-r from-amber-100 to-rose-100 text-amber-800 dark:from-amber-500/10 dark:to-rose-500/10 dark:text-amber-300",
};

const CHANNEL_LABELS: Record<string, string> = {
  webchat: "Web chat",
  whatsapp: "WhatsApp",
  voice: "Voice",
};

export default function BillingPage() {
  const { data, isLoading, isError } = useOrgBilling();

  const dataReady =
    !!data &&
    !!data.plan &&
    !!data.usage &&
    !!data.current_month_costs &&
    Array.isArray(data.by_channel);

  // Pick the first mapped provider→model from pricing_notes as the "active" model
  // display. The deployed billing endpoint doesn't return a `provider` field on
  // its own — it exposes a full provider_model_map instead.
  const providerModelMap = data?.pricing_notes?.provider_model_map ?? {};
  const activeProvider = Object.keys(providerModelMap)[0] ?? "";
  const activeModel = providerModelMap[activeProvider] ?? "—";
  const modelInputPrice =
    data?.pricing_notes?.model_input_price_per_1k?.[activeModel] ?? 0;
  const modelOutputPrice =
    data?.pricing_notes?.model_output_price_per_1k?.[activeModel] ?? 0;

  return (
    <div>
      <div className="flex items-center gap-2">
        <Wallet className="h-6 w-6 text-indigo-500" />
        <h2 className="text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-100">
          Billing
        </h2>
      </div>
      <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
        Your current plan, usage this month, and estimated spend.
      </p>

      {isLoading ? (
        <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Skeleton className="h-40 rounded-xl lg:col-span-2" />
          <Skeleton className="h-40 rounded-xl" />
        </div>
      ) : isError || !dataReady ? (
        <p className="mt-6 text-sm text-rose-600 dark:text-rose-400">Failed to load billing.</p>
      ) : (
        <>
          {/* Plan card + KPIs */}
          <motion.div
            className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3"
            variants={staggerContainer(0.05)}
            initial="hidden"
            animate="show"
          >
            {/* Plan card takes 2/3 */}
            <motion.div variants={itemFadeLeft} className="lg:col-span-2">
              <Card>
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                      Current plan
                    </p>
                    <div className="mt-1 flex items-center gap-3">
                      <h3 className="text-3xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
                        {data.plan.display_name}
                      </h3>
                      <span
                        className={`inline-flex items-center rounded-full px-3 py-0.5 text-xs font-semibold capitalize ${
                          PLAN_TONE[data.plan.key] ?? PLAN_TONE.free
                        }`}
                      >
                        {data.plan.key}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      {data.plan.price_usd_monthly > 0
                        ? `$${data.plan.price_usd_monthly}/month · ${data.plan.monthly_message_quota.toLocaleString()} messages`
                        : data.plan.key === "enterprise"
                        ? "Custom pricing · contact us for quota"
                        : `Free tier · ${data.plan.monthly_message_quota.toLocaleString()} messages/month`}
                    </p>
                  </div>
                  <Button
                    variant="secondary"
                    onClick={() =>
                      window.open(
                        "mailto:sales@genaitech.be?subject=Upgrade%20plan",
                        "_blank",
                      )
                    }
                  >
                    <ArrowUpRight className="h-4 w-4" />
                    {data.plan.key === "enterprise" ? "Talk to us" : "Upgrade"}
                  </Button>
                </div>

                {/* Usage bar */}
                <div className="mt-6">
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="font-medium text-slate-600 dark:text-slate-300">
                      Usage this month
                    </span>
                    <span className="font-mono tabular-nums text-slate-500 dark:text-slate-400">
                      {(data.usage.messages_this_month ?? 0).toLocaleString()} /{" "}
                      {(data.usage.quota ?? 0).toLocaleString()}
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                    <div
                      className={`h-full rounded-full transition-all duration-500 ${
                        data.usage.percent_used > 90
                          ? "bg-rose-500"
                          : data.usage.percent_used > 75
                          ? "bg-amber-500"
                          : "bg-indigo-500"
                      }`}
                      style={{ width: `${Math.min(data.usage.percent_used ?? 0, 100)}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500 dark:text-slate-400">
                    {(data.usage.percent_used ?? 0).toFixed(1)}% used ·{" "}
                    {Math.max(
                      (data.usage.quota ?? 0) - (data.usage.messages_this_month ?? 0),
                      0,
                    ).toLocaleString()}{" "}
                    remaining
                  </p>
                </div>

                {/* Features */}
                <div className="mt-6 border-t border-slate-100 pt-4 dark:border-slate-800">
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    What's included
                  </p>
                  <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {(data.plan.features ?? []).map((f) => (
                      <li key={f} className="flex items-start gap-2 text-sm text-slate-700 dark:text-slate-300">
                        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </Card>
            </motion.div>

            {/* Cost this month card */}
            <motion.div variants={itemFadeLeft}>
              <StatsCard
                label="Estimated cost this month"
                value={`~$${(data.current_month_costs.total_usd ?? 0).toFixed(2)}`}
                tone="indigo"
                icon={<DollarSign className="h-5 w-5" />}
                hint={`${(data.current_month_costs.messages ?? 0).toLocaleString()} AI messages`}
              />
              <div className="mt-6">
                <StatsCard
                  label="Active LLM provider"
                  value={activeModel}
                  tone="amber"
                  icon={<Sparkles className="h-5 w-5" />}
                  hint={
                    activeProvider
                      ? `${activeProvider} · $${modelInputPrice.toFixed(4)} in / $${modelOutputPrice.toFixed(4)} out per 1K tokens`
                      : "No provider configured"
                  }
                />
              </div>
            </motion.div>
          </motion.div>

          {/* Breakdown table */}
          <Card title="Estimated spend breakdown" className="mt-6">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-slate-200 text-xs font-semibold uppercase tracking-wider text-slate-500 dark:border-slate-700 dark:text-slate-400">
                    <th className="pb-3">Line item</th>
                    <th className="pb-3 text-right">Amount (USD)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  <tr>
                    <td className="py-3 text-slate-700 dark:text-slate-300">
                      LLM tokens {activeModel ? `(${activeModel})` : ""}
                    </td>
                    <td className="py-3 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                      ~${(data.current_month_costs.llm_usd ?? 0).toFixed(2)}
                    </td>
                  </tr>
                  <tr>
                    <td className="py-3 text-slate-700 dark:text-slate-300">
                      External APIs (Retell, WhatsApp, etc.)
                    </td>
                    <td className="py-3 text-right font-mono tabular-nums text-slate-700 dark:text-slate-300">
                      ~${(data.current_month_costs.external_usd ?? 0).toFixed(2)}
                    </td>
                  </tr>
                  <tr className="bg-slate-50/50 dark:bg-slate-800/30">
                    <td className="py-3 font-semibold text-slate-900 dark:text-slate-100">
                      Total this month
                    </td>
                    <td className="py-3 text-right font-mono text-base font-bold tabular-nums text-slate-900 dark:text-slate-100">
                      ~${(data.current_month_costs.total_usd ?? 0).toFixed(2)}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          {/* By channel */}
          {data.by_channel.length > 0 && (
            <Card title="By channel" className="mt-6">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {data.by_channel.map((c) => (
                  <div
                    key={c.channel}
                    className="rounded-lg border border-slate-200 p-4 dark:border-slate-700"
                  >
                    <div className="flex items-start justify-between">
                      <p className="text-sm font-medium text-slate-600 dark:text-slate-300">
                        {CHANNEL_LABELS[c.channel] ?? c.channel}
                      </p>
                      <MessageSquare className="h-4 w-4 text-slate-400" />
                    </div>
                    <p className="mt-2 text-2xl font-bold tabular-nums text-slate-900 dark:text-slate-100">
                      ~${(c.total_usd ?? 0).toFixed(2)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                      {(c.messages ?? 0).toLocaleString()} AI messages
                    </p>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Plan tier comparison — footer */}
          <Card title="Available plans" className="mt-6">
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {PLAN_ORDER.map((k) => {
                const isCurrent = k === data.plan.key;
                return (
                  <div
                    key={k}
                    className={`rounded-lg border-2 p-4 transition-all ${
                      isCurrent
                        ? "border-indigo-500 bg-indigo-50/50 dark:border-indigo-400 dark:bg-indigo-500/10"
                        : "border-slate-200 dark:border-slate-700"
                    }`}
                  >
                    <p className="text-xs font-semibold uppercase capitalize tracking-wider text-slate-500 dark:text-slate-400">
                      {k}
                    </p>
                    <p className="mt-1 text-base font-bold capitalize text-slate-900 dark:text-slate-100">
                      {k === "enterprise" ? "Custom" : k === "free" ? "$0" : k === "starter" ? "$29/mo" : "$99/mo"}
                    </p>
                    {isCurrent && (
                      <p className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-indigo-600 dark:text-indigo-400">
                        <CheckCircle2 className="h-3 w-3" />
                        Current
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="mt-4 text-xs text-slate-500 dark:text-slate-400">
              All figures are estimates based on message volume × current provider rates. Actual
              provider bills are the source of truth.
            </p>
          </Card>
        </>
      )}
    </div>
  );
}
