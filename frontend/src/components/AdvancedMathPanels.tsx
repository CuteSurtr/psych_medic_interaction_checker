import { useCallback, useState } from "react";
import { apiUrl } from "../utils/api";
import ErrorBoundary from "./ErrorBoundary";

/* ─── shared plumbing ─────────────────────────────────────────── */

interface Async<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

const blank = <T,>(): Async<T> => ({ data: null, loading: false, error: null });

/** Formats a value that the API may legitimately return as null.
 *  Every nullable field goes through here: a `null` reaching `.toFixed`
 *  is what blanked this page once already. */
function num(v: number | null | undefined, digits = 2, suffix = ""): string {
  return v == null || !Number.isFinite(v) ? "—" : `${v.toFixed(digits)}${suffix}`;
}

function useEndpoint<T>(path: string) {
  const [state, setState] = useState<Async<T>>(blank<T>());
  const run = useCallback(
    async (body: unknown) => {
      setState({ data: null, loading: true, error: null });
      try {
        const res = await fetch(apiUrl(path), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => null);
          throw new Error(detail?.detail ?? `${res.status} ${res.statusText}`);
        }
        setState({ data: (await res.json()) as T, loading: false, error: null });
      } catch (err) {
        setState({ data: null, loading: false, error: (err as Error).message });
      }
    },
    [path],
  );
  return [state, run] as const;
}

export interface PkCandidate {
  id: number;
  generic_name: string;
  has_pk_parameters?: boolean;
}

/** First regimen entry that can actually drive the compartmental model.
 *  Roughly half the formulary carries interaction and CYP data but no
 *  clearance, volume or absorption rate, and picking blindly by position made
 *  these panels fail on whichever drug happened to be added first. */
function pickPkCandidate(candidates: PkCandidate[]): PkCandidate | null {
  return candidates.find((c) => c.has_pk_parameters) ?? null;
}

function NoPkNotice({ candidates }: { candidates: PkCandidate[] }) {
  return (
    <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
      {candidates.length === 0
        ? "Add a medication to run this analysis."
        : "None of the medications in this regimen has the clearance, volume of distribution and absorption rate this analysis needs. Around half the formulary carries interaction and CYP450 data only; half-life alone cannot recover them. Try fluoxetine, bupropion, aripiprazole, lithium or clozapine."}
    </p>
  );
}

function Panel({
  title,
  tag,
  blurb,
  subject,
  notice,
  state,
  onRun,
  disabled,
  children,
}: {
  title: string;
  tag: string;
  blurb: string;
  subject?: string | null;
  notice?: React.ReactNode;
  state: Async<unknown>;
  onRun: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-sm font-bold text-slate-800">{title}</span>
            <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
              {tag}
            </span>
          </div>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-slate-500">{blurb}</p>
          {subject && (
            <p className="mt-1 text-[11px] font-medium text-indigo-600">Analysing: {subject}</p>
          )}
        </div>
        <button
          type="button"
          onClick={onRun}
          disabled={disabled || state.loading}
          className="shrink-0 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {state.loading ? "Running…" : "Compute"}
        </button>
      </div>
      {notice && <div className="px-5 pb-4">{notice}</div>}
      {(state.error || state.data != null) && (
        <div className="border-t border-slate-100 px-5 py-4">
          {state.error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {state.error}
            </div>
          )}
          {state.data != null && <ErrorBoundary label={title}>{children}</ErrorBoundary>}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-bold text-slate-800">{value}</p>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
    </div>
  );
}

function Bar({ label, value, max, warn }: { label: string; value: number; max: number; warn?: boolean }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="flex items-center gap-2 py-0.5">
      <span className="w-24 truncate text-right text-xs text-slate-600">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full ${warn ? "bg-amber-500" : "bg-indigo-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-14 text-xs text-slate-600">{num(value, 3)}</span>
    </div>
  );
}

/* ─── 1. D-optimal sampling design ────────────────────────────── */

interface DesignData {
  drug_name: string | null;
  optimal_times_h: number[];
  reference_times_h: number[] | null;
  d_efficiency_of_reference_pct: number | null;
  relative_standard_errors_pct: Record<string, number>;
  condition_number: number | null;
  grid_step_h: number;
}

export function OptimalDesignPanel({ candidates }: { candidates: PkCandidate[] }) {
  const pick = pickPkCandidate(candidates);
  const [state, run] = useEndpoint<DesignData>("/api/advanced/optimal-design");
  const [nSamples, setNSamples] = useState(3);
  const d = state.data;
  return (
    <Panel
      title="Optimal Sampling Design"
      tag="Fisher Information"
      blurb="When should the levels actually be drawn? Maximises the determinant of the Fisher information matrix over sampling times, and scores routine trough-only monitoring against it."
      state={state}
      subject={pick?.generic_name}
      notice={pick == null ? <NoPkNotice candidates={candidates} /> : null}
      disabled={pick == null}
      onRun={() => pick && run({ medication_id: pick.id, n_samples: nSamples })}
    >
      {d && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat
              label="D-optimal times"
              value={d.optimal_times_h.map((t) => `${t}h`).join(", ")}
              sub={`grid step ${num(d.grid_step_h, 2)} h`}
            />
            <Stat
              label="Trough-only efficiency"
              value={num(d.d_efficiency_of_reference_pct, 1, "%")}
              sub="D-efficiency of the reference schedule"
            />
            <Stat label="Condition number" value={num(d.condition_number, 1)} sub="of the information matrix" />
          </div>
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              Relative standard error at the optimal design
            </p>
            {Object.entries(d.relative_standard_errors_pct).map(([k, v]) => (
              <Bar key={k} label={k} value={v} max={200} warn={v > 50} />
            ))}
          </div>
          {d.d_efficiency_of_reference_pct != null && d.d_efficiency_of_reference_pct < 25 && (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              The reference schedule carries under a quarter of the information of the optimal one. The
              samples are real; the information is close to nil.
            </p>
          )}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <label htmlFor="nsamp">Samples</label>
        <input
          id="nsamp"
          type="number"
          min={2}
          max={6}
          value={nSamples}
          onChange={(e) => setNSamples(Number(e.target.value))}
          className="w-16 rounded border border-slate-300 px-2 py-1"
        />
      </div>
    </Panel>
  );
}

/* ─── 2. Sobol sensitivity ────────────────────────────────────── */

interface SobolData {
  metric: string;
  first_order: Record<string, number>;
  total_order: Record<string, number>;
  interaction: Record<string, number>;
  dominant_parameter: string;
  ranking: string[];
  sum_first_order: number;
  converged: boolean;
  warnings: string[];
  n_model_evaluations: number;
}

const METRICS = ["cmax", "auc", "trough", "tmax"] as const;

export function SensitivityPanel({ candidates }: { candidates: PkCandidate[] }) {
  const pick = pickPkCandidate(candidates);
  const [state, run] = useEndpoint<SobolData>("/api/advanced/sensitivity");
  const [metric, setMetric] = useState<string>("cmax");
  const d = state.data;
  return (
    <Panel
      title="Global Sensitivity"
      tag="Sobol Indices"
      blurb="Which parameter's uncertainty drives the predicted exposure, and how much of that is carried through interactions rather than alone. Variance decomposition over the whole input distribution, not one-at-a-time."
      state={state}
      subject={pick?.generic_name}
      notice={pick == null ? <NoPkNotice candidates={candidates} /> : null}
      disabled={pick == null}
      onRun={() => pick && run({ medication_id: pick.id, metric })}
    >
      {d && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat label="Dominant parameter" value={d.dominant_parameter} sub={`ranking: ${d.ranking.join(" > ")}`} />
            <Stat
              label="Sum of first-order"
              value={num(d.sum_first_order, 2)}
              sub={d.sum_first_order > 0.95 ? "essentially additive" : "interactions carry the rest"}
            />
            <Stat label="Model evaluations" value={String(d.n_model_evaluations)} sub={`metric: ${d.metric}`} />
          </div>
          <div>
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
              First-order (alone) vs total-effect (including interactions)
            </p>
            {Object.keys(d.total_order).map((k) => (
              <div key={k} className="py-1">
                <Bar label={`${k} · S`} value={d.first_order[k] ?? 0} max={1} />
                <Bar label={`${k} · Sᴛ`} value={d.total_order[k] ?? 0} max={1} warn />
              </div>
            ))}
          </div>
          {!d.converged && d.warnings.length > 0 && (
            <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
              <p className="font-semibold">Not converged</p>
              <ul className="mt-1 list-disc pl-4">
                {d.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <label htmlFor="metric">Metric</label>
        <select
          id="metric"
          value={metric}
          onChange={(e) => setMetric(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1"
        >
          {METRICS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>
    </Panel>
  );
}

/* ─── 3. Treatment policy (MDP) ───────────────────────────────── */

interface PolicyData {
  states: string[];
  policy: Record<string, string>;
  value_function: Record<string, number>;
  best_constant_action: string;
  advantage_over_best_constant: number;
  constant_policy_values: Record<string, number>;
  n_iterations: number;
  converged: boolean;
  value_iteration_agrees: boolean;
  discount: number;
}

export function TreatmentPolicyPanel() {
  const [state, run] = useEndpoint<PolicyData>("/api/advanced/treatment-policy");
  const [discount, setDiscount] = useState(0.95);
  const d = state.data;
  return (
    <Panel
      title="Optimal Treatment Policy"
      tag="Markov Decision Process"
      blurb="Turns the descriptive patient-state chain prescriptive: which drug class is optimal in each clinical state, solved by policy iteration and cross-checked against value iteration."
      state={state}
      onRun={() => run({ discount })}
    >
      {d && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat
              label="Gain over constant regimen"
              value={num(d.advantage_over_best_constant, 2)}
              sub={`best constant: ${d.best_constant_action}`}
            />
            <Stat label="Policy iterations" value={String(d.n_iterations)} sub={d.converged ? "terminated exactly" : "hit the cap"} />
            <Stat
              label="Solver cross-check"
              value={d.value_iteration_agrees ? "agree" : "DISAGREE"}
              sub="value iteration vs policy iteration"
            />
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-left text-slate-500">
                  <th className="px-2 py-1">Clinical state</th>
                  <th className="px-2 py-1">Optimal action</th>
                  <th className="px-2 py-1 text-right">V(s)</th>
                </tr>
              </thead>
              <tbody>
                {d.states.map((s) => (
                  <tr key={s} className="border-t border-slate-100">
                    <td className="px-2 py-1.5 text-slate-700">{s}</td>
                    <td className="px-2 py-1.5">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                          d.policy[s] === "none"
                            ? "bg-slate-100 text-slate-600"
                            : "bg-indigo-50 text-indigo-700"
                        }`}
                      >
                        {d.policy[s] === "none" ? "watchful waiting" : d.policy[s]}
                      </span>
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">
                      {num(d.value_function[s], 2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-[11px] leading-relaxed text-slate-400">
            Values are on an arbitrary utility scale, so only differences between policies are meaningful.
          </p>
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <label htmlFor="disc">Discount γ</label>
        <input
          id="disc"
          type="number"
          step={0.01}
          min={0.01}
          max={0.99}
          value={discount}
          onChange={(e) => setDiscount(Number(e.target.value))}
          className="w-20 rounded border border-slate-300 px-2 py-1"
        />
      </div>
    </Panel>
  );
}

/* ─── 4. Identifiability ──────────────────────────────────────── */

interface ProfileRow {
  parameter: string;
  mle: number;
  ci_lower: number | null;
  ci_upper: number | null;
  identifiable: boolean;
  verdict: string;
}

interface IdentData {
  rank: number;
  n_parameters: number;
  structurally_identifiable: boolean;
  practically_identifiable: boolean;
  collinearity_index: number | null;
  collinearity_index_is_infinite: boolean;
  worst_constrained_direction: Record<string, number>;
  notes: string[];
  profiles: ProfileRow[];
}

const SCHEDULES: Record<string, number[]> = {
  "Rich (0.5,1,2,4,8,18h)": [0.5, 1, 2, 4, 8, 18],
  "Peak + trough (2,24h)": [2, 24],
  "Trough only (22,23,24h)": [22, 23, 24],
  "Single time x3 (24,24,24h)": [24, 24, 24],
};

export function IdentifiabilityPanel({ candidates }: { candidates: PkCandidate[] }) {
  const pick = pickPkCandidate(candidates);
  const [state, run] = useEndpoint<IdentData>("/api/advanced/identifiability");
  const [schedule, setSchedule] = useState<string>(Object.keys(SCHEDULES)[0]);
  const d = state.data;
  return (
    <Panel
      title="Identifiability"
      tag="Rank + Profile Likelihood"
      blurb="Can these parameters be recovered from this sampling schedule at all? Structural failure comes from the rank and collinearity of the sensitivity matrix; practical failure from a likelihood profile that never closes."
      state={state}
      subject={pick?.generic_name}
      notice={pick == null ? <NoPkNotice candidates={candidates} /> : null}
      disabled={pick == null}
      onRun={() => pick && run({ medication_id: pick.id, sampling_times_h: SCHEDULES[schedule] })}
    >
      {d && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat label="Sensitivity rank" value={`${d.rank} / ${d.n_parameters}`} sub={d.rank < d.n_parameters ? "rank deficient" : "full rank"} />
            <Stat
              label="Collinearity index γ"
              value={d.collinearity_index_is_infinite ? "∞" : num(d.collinearity_index, 1)}
              sub="above ~20 is not separable"
            />
            <Stat
              label="Verdict"
              value={d.structurally_identifiable && d.practically_identifiable ? "identifiable" : "not identifiable"}
              sub={`structural ${d.structurally_identifiable ? "ok" : "fail"} · practical ${d.practically_identifiable ? "ok" : "fail"}`}
            />
          </div>
          {d.profiles.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left text-slate-500">
                    <th className="px-2 py-1">Parameter</th>
                    <th className="px-2 py-1 text-right">MLE</th>
                    <th className="px-2 py-1">95% interval</th>
                    <th className="px-2 py-1">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {d.profiles.map((p) => (
                    <tr key={p.parameter} className="border-t border-slate-100">
                      <td className="px-2 py-1.5 text-slate-700">{p.parameter}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">{num(p.mle, 3)}</td>
                      <td className="px-2 py-1.5 tabular-nums text-slate-600">
                        [{num(p.ci_lower, 3)}, {num(p.ci_upper, 3)}]
                      </td>
                      <td className="px-2 py-1.5">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            p.identifiable ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"
                          }`}
                        >
                          {p.identifiable ? "bounded" : "unbounded"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {d.notes.length > 0 && (
            <ul className="list-disc space-y-1 rounded-lg bg-amber-50 px-5 py-2 text-xs text-amber-800">
              {d.notes.map((n, i) => (
                <li key={i}>{n}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
        <label htmlFor="sched">Schedule</label>
        <select
          id="sched"
          value={schedule}
          onChange={(e) => setSchedule(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1"
        >
          {Object.keys(SCHEDULES).map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
      </div>
    </Panel>
  );
}
