import { useState, useCallback } from "react";
import type { MedicationSearchHit, RegimenItem } from "../types";
import { apiUrl } from "../utils/api";
import AppHeader from "../components/AppHeader";
import MedicationSearch from "../components/MedicationSearch";
import RegimenList from "../components/RegimenList";
import DisclaimerFooter from "../components/DisclaimerFooter";

/* ─── Response types ──────────────────────────────────────────── */

interface GraphMetricsData {
  fiedler_value: number;
  spectral_radius: number;
  bridge_drug: string | null;
  chromatic_number: number;
  independence_number: number;
  /** Backend field name (largest safe subset of drugs). */
  max_safe_subset: string[];
  adjacency_matrix: number[][];
  drug_names: string[];
}

interface BipartiteData {
  conflicts_per_enzyme: Record<string, number>;
  total_conflicts: number;
  minimum_cover: string[];
  singular_values: number[];
}

interface MetabolicFlowData {
  bottleneck_enzyme: string | null;
  /** Already a percentage 0–100 from the API. */
  bottleneck_utilization_pct: number;
  /** Per-enzyme utilisation, 0–100. */
  enzyme_utilizations: Record<string, number>;
  max_flow: number;
}

interface ThreeDrugIxRow {
  drug_classes?: string[][];
  description: string;
  severity: string;
  recommendation?: string;
}

interface CombinatoricsData {
  pairwise_checks: number;
  triple_checks: number;
  detected_three_drug_interactions: ThreeDrugIxRow[];
  conflict_probability_pct?: number;
}

interface EntropyData {
  cdi: number;
  entropy_bits: number;
  max_entropy: number;
  dominant_enzyme: string;
  dominant_enzyme_pct: number;
  interpretation: string;
  load_distribution: Record<string, number>;
}

interface TopologyData {
  betti_0: number;
  betti_1: number;
  has_feedback_loops: boolean;
  total_persistence: number;
  persistence_features: { dimension: number; birth: number; death: number }[];
}

/** Matches FastAPI `/api/advanced/game-theory` JSON. */
interface GameTheoryApiResponse {
  price_of_anarchy: number;
  social_cost: number;
  ideal_clearances: Record<string, number>;
  effective_clearances: Record<string, number>;
  clearance_reduction_pct: Record<string, number>;
  enzyme_competition_matrix: Record<string, Record<string, number>>;
}

interface MarkovData {
  stationary_distribution: Record<string, number>;
  first_passage_times: Record<string, Record<string, number>>;
  trajectory_summary: Record<string, number>;
}

/* ─── Async wrapper ───────────────────────────────────────────── */

interface Async<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

function blank<T>(): Async<T> {
  return { data: null, loading: false, error: null };
}

/* ─── Reusable tiny components ────────────────────────────────── */

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={`h-5 w-5 text-slate-400 transition-transform ${open ? "rotate-180" : ""}`}
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 20 20"
      fill="currentColor"
    >
      <path
        fillRule="evenodd"
        d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function Spinner() {
  return (
    <div className="flex items-center justify-center py-10">
      <svg className="h-6 w-6 animate-spin text-indigo-500" viewBox="0 0 24 24" fill="none">
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
    </div>
  );
}

function ErrorBox({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {message}
    </div>
  );
}

function Stat({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-bold text-slate-800">{value}</p>
      {sub && <p className="mt-1.5 text-xs leading-relaxed text-slate-500">{sub}</p>}
    </div>
  );
}

function HBar({
  label,
  value,
  max,
  warn,
  format,
}: {
  label: string;
  value: number;
  max: number;
  warn?: boolean;
  format?: (v: number) => string;
}) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div className="flex items-center gap-2 py-1">
      <span className="w-28 truncate text-right text-xs text-slate-600">{label}</span>
      <div className="h-3 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all ${warn ? "bg-red-500" : "bg-indigo-500"}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-14 text-xs text-slate-600">{format ? format(value) : value.toFixed(2)}</span>
    </div>
  );
}

function Section({
  title,
  tag,
  open,
  onToggle,
  loading,
  error,
  hasData,
  children,
}: {
  title: string;
  tag: string;
  open: boolean;
  onToggle: () => void;
  loading: boolean;
  error: string | null;
  hasData: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center justify-between px-5 py-4 text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold text-slate-800">{title}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
            {tag}
          </span>
        </div>
        <ChevronIcon open={open} />
      </button>

      {open && (
        <div className="border-t border-slate-100 px-5 py-4">
          {loading && <Spinner />}
          {!loading && error && <ErrorBox message={error} />}
          {!loading && !error && !hasData && (
            <p className="py-6 text-center text-sm text-slate-400">
              Click &ldquo;Run Analysis&rdquo; to populate this section.
            </p>
          )}
          {!loading && !error && hasData && children}
        </div>
      )}
    </div>
  );
}

function ColorGrid({
  matrix,
  rowLabels,
  colLabels,
  hue = "indigo",
}: {
  matrix: number[][];
  rowLabels: string[];
  colLabels: string[];
  hue?: "indigo" | "amber";
}) {
  const flat = matrix.flat().map(Math.abs);
  const maxVal = Math.max(...flat, 0.001);
  const bgBase = hue === "indigo" ? [99, 102, 241] : [245, 158, 11];

  return (
    <div className="overflow-x-auto">
      <table className="text-xs">
        <thead>
          <tr>
            <th className="px-1 py-1" />
            {colLabels.map((c) => (
              <th
                key={c}
                className="max-w-[80px] truncate px-2 py-1 font-medium text-slate-500"
                title={c}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.map((row, i) => (
            <tr key={i}>
              <td className="whitespace-nowrap pr-2 py-1 text-right font-medium text-slate-600">
                {rowLabels[i] ?? i}
              </td>
              {row.map((val, j) => {
                const t = Math.abs(val) / maxVal;
                const alpha = t * 0.7 + 0.05;
                return (
                  <td
                    key={j}
                    className="px-2 py-1.5 text-center"
                    style={{
                      backgroundColor: `rgba(${bgBase.join(",")},${alpha.toFixed(2)})`,
                      color: t > 0.55 ? "#fff" : "#334155",
                    }}
                  >
                    {val.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ─── CDI Gauge ───────────────────────────────────────────────── */

function CDIGauge({ value }: { value: number }) {
  const clamped = Math.max(0, Math.min(value, 1));
  const circumference = 2 * Math.PI * 50;
  const stroke =
    clamped >= 0.8 ? "#22c55e" : clamped >= 0.5 ? "#eab308" : "#ef4444";
  const bg =
    clamped >= 0.8
      ? "text-green-600"
      : clamped >= 0.5
        ? "text-yellow-600"
        : "text-red-600";

  return (
    <svg viewBox="0 0 120 120" className="mx-auto h-36 w-36">
      <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" strokeWidth="8" />
      <circle
        cx="60"
        cy="60"
        r="50"
        fill="none"
        stroke={stroke}
        strokeWidth="8"
        strokeDasharray={`${clamped * circumference} ${circumference}`}
        strokeLinecap="round"
        transform="rotate(-90 60 60)"
      />
      <text
        x="60"
        y="55"
        textAnchor="middle"
        dominantBaseline="central"
        className={`text-2xl font-bold ${bg}`}
        fill="currentColor"
      >
        {clamped.toFixed(2)}
      </text>
      <text
        x="60"
        y="75"
        textAnchor="middle"
        className="text-[9px] font-medium text-slate-400"
        fill="currentColor"
      >
        CDI
      </text>
    </svg>
  );
}

/* ─── Main component ──────────────────────────────────────────── */

export default function Analysis() {
  /* regimen state (same pattern as Dashboard) */
  const [regimen, setRegimen] = useState<RegimenItem[]>([]);

  const addMed = (hit: MedicationSearchHit) => {
    setRegimen((prev) => {
      if (prev.some((m) => m.id === hit.id)) return prev;
      return [...prev, { ...hit }];
    });
  };
  const removeMed = (id: number) => setRegimen((prev) => prev.filter((m) => m.id !== id));
  const clearRegimen = () => {
    setRegimen([]);
    setGraph(blank());
    setBipartite(blank());
    setFlow(blank());
    setCombi(blank());
    setEntropy(blank());
    setTopo(blank());
    setGame(blank());
    setMarkov(blank());
  };
  const changeDosage = (id: number, dosage: string) =>
    setRegimen((prev) => prev.map((m) => (m.id === id ? { ...m, dosage } : m)));

  /* analysis results */
  const [graph, setGraph] = useState<Async<GraphMetricsData>>(blank);
  const [bipartite, setBipartite] = useState<Async<BipartiteData>>(blank);
  const [flow, setFlow] = useState<Async<MetabolicFlowData>>(blank);
  const [combi, setCombi] = useState<Async<CombinatoricsData>>(blank);
  const [entropy, setEntropy] = useState<Async<EntropyData>>(blank);
  const [topo, setTopo] = useState<Async<TopologyData>>(blank);
  const [game, setGame] = useState<Async<GameTheoryApiResponse>>(blank);
  const [markov, setMarkov] = useState<Async<MarkovData>>(blank);

  /* section toggles */
  const [open, setOpen] = useState<Record<string, boolean>>({
    graph: true,
    bipartite: true,
    flow: true,
    combi: true,
    entropy: true,
    topo: true,
    game: true,
    markov: true,
  });
  const toggle = (k: string) => setOpen((p) => ({ ...p, [k]: !p[k] }));

  /* fetch helper */
  async function fetchTo<T>(
    url: string,
    setter: React.Dispatch<React.SetStateAction<Async<T>>>,
    init?: RequestInit,
  ) {
    try {
      const res = await fetch(apiUrl(url), init);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: T = await res.json();
      setter({ data, loading: false, error: null });
    } catch (err) {
      setter({ data: null, loading: false, error: (err as Error).message });
    }
  }

  const runAnalysis = useCallback(async () => {
    if (regimen.length < 2) return;

    const ids = regimen.map((m) => m.id).join(",");
    const idArray = regimen.map((m) => m.id);
    const drugClasses = [...new Set(regimen.map((m) => m.drug_class))];
    const jsonHeaders = { "Content-Type": "application/json" };

    const loading: Async<never> = { data: null, loading: true, error: null };
    setGraph(loading);
    setBipartite(loading);
    setFlow(loading);
    setCombi(loading);
    setEntropy(loading);
    setTopo(loading);
    setGame(loading);
    setMarkov(loading);

    await Promise.allSettled([
      fetchTo<GraphMetricsData>(`/api/analysis/graph-metrics?medication_ids=${ids}`, setGraph),
      fetchTo<BipartiteData>(`/api/analysis/bipartite-metrics?medication_ids=${ids}`, setBipartite),
      fetchTo<MetabolicFlowData>(`/api/analysis/metabolic-flow?medication_ids=${ids}`, setFlow),
      fetchTo<CombinatoricsData>(`/api/analysis/combinatorics?medication_ids=${ids}`, setCombi),
      fetchTo<EntropyData>(`/api/advanced/entropy?medication_ids=${ids}`, setEntropy),
      fetchTo<TopologyData>(`/api/advanced/topology?medication_ids=${ids}`, setTopo),
      fetchTo<GameTheoryApiResponse>("/api/advanced/game-theory", setGame, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify({ medication_ids: idArray }),
      }),
      fetchTo<MarkovData>("/api/advanced/markov", setMarkov, {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify({
          drug_classes: drugClasses,
          initial_state: "Partial Response",
          n_weeks: 52,
        }),
      }),
    ]);
  }, [regimen]);

  const anyTriggered =
    graph.loading || graph.data !== null || graph.error !== null;

  /* ── render ──────────────────────────────────────────────────── */

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans">
      <AppHeader title="Advanced Analysis" />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* ── Regimen builder ──────────────────────────────────── */}
        <MedicationSearch onSelect={addMed} />
        <RegimenList
          items={regimen}
          onRemove={removeMed}
          onClear={clearRegimen}
          onDosageChange={changeDosage}
        />

        <button
          type="button"
          disabled={regimen.length < 2}
          onClick={runAnalysis}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/40 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
            <path
              fillRule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1.5-11.5a.75.75 0 011.28-.53l3.5 3.25a.75.75 0 010 1.06l-3.5 3.25a.75.75 0 01-1.28-.53v-6.5z"
              clipRule="evenodd"
            />
          </svg>
          Run Analysis
        </button>

        {regimen.length > 0 && regimen.length < 2 && (
          <p className="text-xs text-amber-600">Add at least 2 medications to run analysis.</p>
        )}

        {!anyTriggered && regimen.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
            <p className="text-sm text-slate-500">
              Add medications above, then click <strong>Run Analysis</strong> to
              view graph-theory and advanced-math metrics.
            </p>
          </div>
        )}

        {/* ── Section 1 : Graph Metrics ────────────────────────── */}
        {anyTriggered && (
          <Section
            title="Graph Metrics"
            tag="Spectral Graph Theory"
            open={open.graph}
            onToggle={() => toggle("graph")}
            loading={graph.loading}
            error={graph.error}
            hasData={graph.data !== null}
          >
            {graph.data && (() => {
              const d = graph.data;
              return (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat
                      label="Regimen Coupling (λ₂)"
                      value={d.fiedler_value.toFixed(4)}
                      sub={
                        d.fiedler_value === 0
                          ? "Disconnected — some drugs don't interact"
                          : d.fiedler_value < 0.5
                            ? "Loosely coupled regimen"
                            : "Tightly coupled — interactions are widespread"
                      }
                    />
                    <Stat
                      label="Max Interaction Intensity ρ(W)"
                      value={d.spectral_radius.toFixed(4)}
                    />
                    <Stat
                      label="Compatibility Phases (χ)"
                      value={d.chromatic_number}
                      sub={`Requires ${d.chromatic_number} compatibility phase${d.chromatic_number !== 1 ? "s" : ""}`}
                    />
                    <Stat
                      label="Max Safe Subset"
                      value={`${d.independence_number} drug${d.independence_number !== 1 ? "s" : ""}`}
                      sub={(d.max_safe_subset ?? []).join(", ") || "—"}
                    />
                  </div>

                  {d.bridge_drug && (
                    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                      Removing <strong>{d.bridge_drug}</strong> would most reduce
                      overall interaction burden.
                    </div>
                  )}

                  {d.adjacency_matrix.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Adjacency Matrix
                      </p>
                      <ColorGrid
                        matrix={d.adjacency_matrix}
                        rowLabels={d.drug_names}
                        colLabels={d.drug_names}
                      />
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 2 : CYP450 Bipartite Analysis ────────────── */}
        {anyTriggered && (
          <Section
            title="CYP450 Bipartite Analysis"
            tag="Bipartite Matching"
            open={open.bipartite}
            onToggle={() => toggle("bipartite")}
            loading={bipartite.loading}
            error={bipartite.error}
            hasData={bipartite.data !== null}
          >
            {bipartite.data && (() => {
              const d = bipartite.data;
              const entries = Object.entries(d.conflicts_per_enzyme);
              const maxConflicts = Math.max(...entries.map(([, v]) => v), 1);
              return (
                <div className="space-y-5">
                  <Stat label="Total Conflicts" value={d.total_conflicts} />

                  {entries.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Conflicts per Enzyme
                      </p>
                      {entries.map(([enzyme, cnt]) => (
                        <HBar
                          key={enzyme}
                          label={enzyme}
                          value={cnt}
                          max={maxConflicts}
                          warn={cnt >= maxConflicts * 0.8}
                          format={(v) => String(Math.round(v))}
                        />
                      ))}
                    </div>
                  )}

                  {d.minimum_cover.length > 0 && (
                    <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-800">
                      Removing{" "}
                      <strong>{d.minimum_cover.join(", ")}</strong> would resolve{" "}
                      {d.total_conflicts} conflict
                      {d.total_conflicts !== 1 ? "s" : ""}.
                    </div>
                  )}

                  {d.singular_values.length > 0 && (
                    <div>
                      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Singular Values
                      </p>
                      <p className="text-xs text-slate-600">
                        {d.singular_values.map((v) => v.toFixed(3)).join(", ")}
                      </p>
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 3 : Metabolic Flow ───────────────────────── */}
        {anyTriggered && (
          <Section
            title="Metabolic Flow"
            tag="Network Flow"
            open={open.flow}
            onToggle={() => toggle("flow")}
            loading={flow.loading}
            error={flow.error}
            hasData={flow.data !== null}
          >
            {flow.data && (() => {
              const d = flow.data;
              const entries = Object.entries(d.enzyme_utilizations);
              return (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <Stat label="Max Flow" value={d.max_flow.toFixed(3)} />
                    <Stat
                      label="Bottleneck Enzyme"
                      value={d.bottleneck_enzyme ?? "—"}
                      sub={`${(d.bottleneck_utilization_pct ?? 0).toFixed(1)}% utilisation`}
                    />
                  </div>

                  {entries.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Enzyme Utilisation
                      </p>
                      {entries.map(([enzyme, util]) => (
                        <HBar
                          key={enzyme}
                          label={enzyme}
                          value={util}
                          max={100}
                          warn={util > 80}
                          format={(v) => `${v.toFixed(1)}%`}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 4 : Combinatorics ────────────────────────── */}
        {anyTriggered && (
          <Section
            title="Combinatorics"
            tag="Inclusion-Exclusion"
            open={open.combi}
            onToggle={() => toggle("combi")}
            loading={combi.loading}
            error={combi.error}
            hasData={combi.data !== null}
          >
            {combi.data && (() => {
              const d = combi.data;
              return (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <Stat label="Pairwise Checks" value={d.pairwise_checks} />
                    <Stat label="Triple Checks" value={d.triple_checks} />
                    {d.conflict_probability_pct !== undefined && (
                      <Stat
                        label="Conflict Probability"
                        value={`${d.conflict_probability_pct.toFixed(1)}%`}
                      />
                    )}
                  </div>

                  {d.detected_three_drug_interactions.length > 0 && (
                    <div className="space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Three-Drug Interactions Detected
                      </p>
                      {d.detected_three_drug_interactions.map((ix, i) => {
                        const title =
                          ix.drug_classes?.length ?
                            ix.drug_classes.map((g) => g.join("/")).join(" + ")
                          : "Pattern match";
                        return (
                        <div
                          key={i}
                          className={`rounded-lg border px-4 py-3 text-sm ${
                            ix.severity === "severe" || ix.severity === "critical"
                              ? "border-red-200 bg-red-50 text-red-800"
                              : ix.severity === "moderate"
                                ? "border-amber-200 bg-amber-50 text-amber-800"
                                : "border-slate-200 bg-slate-50 text-slate-700"
                          }`}
                        >
                          <span className="font-semibold">{title}</span>
                          <p className="mt-1 text-xs leading-relaxed">{ix.description}</p>
                          {ix.recommendation && (
                            <p className="mt-1 text-xs text-slate-600">{ix.recommendation}</p>
                          )}
                        </div>
                        );
                      })}
                    </div>
                  )}

                  {d.detected_three_drug_interactions.length === 0 && (
                    <p className="text-sm text-green-700">
                      No three-drug interactions detected.
                    </p>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 5 : Metabolic Entropy ────────────────────── */}
        {anyTriggered && (
          <Section
            title="Metabolic Entropy"
            tag="Information Theory"
            open={open.entropy}
            onToggle={() => toggle("entropy")}
            loading={entropy.loading}
            error={entropy.error}
            hasData={entropy.data !== null}
          >
            {entropy.data && (() => {
              const d = entropy.data;
              const loadEntries = Object.entries(d.load_distribution);
              const maxLoad = Math.max(...loadEntries.map(([, v]) => v), 0.01);
              return (
                <div className="space-y-5">
                  <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-start">
                    <CDIGauge value={d.cdi} />

                    <div className="flex-1 space-y-3">
                      <div className="grid grid-cols-2 gap-3">
                        <Stat
                          label="Entropy"
                          value={`${d.entropy_bits.toFixed(3)} bits`}
                          sub={`Max ${d.max_entropy.toFixed(3)} bits`}
                        />
                        <Stat
                          label="Dominant Enzyme"
                          value={d.dominant_enzyme}
                          sub={`${d.dominant_enzyme_pct.toFixed(1)}% of total load`}
                        />
                      </div>

                      {d.interpretation && (
                        <p className="rounded-lg bg-slate-50 px-4 py-3 text-xs leading-relaxed text-slate-600">
                          {d.interpretation}
                        </p>
                      )}
                    </div>
                  </div>

                  {loadEntries.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Load Distribution
                      </p>
                      {loadEntries.map(([enzyme, load]) => (
                        <HBar key={enzyme} label={enzyme} value={load} max={maxLoad} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 6 : Topological Data Analysis ────────────── */}
        {anyTriggered && (
          <Section
            title="Topological Data Analysis"
            tag="Persistent Homology"
            open={open.topo}
            onToggle={() => toggle("topo")}
            loading={topo.loading}
            error={topo.error}
            hasData={topo.data !== null}
          >
            {topo.data && (() => {
              const d = topo.data;
              return (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                    <Stat label="β₀ (Components)" value={d.betti_0} />
                    <Stat label="β₁ (Loops)" value={d.betti_1} />
                    <Stat label="Total Persistence" value={d.total_persistence.toFixed(4)} />
                    <div className="flex items-center justify-center rounded-lg border border-slate-200 bg-white p-4">
                      <span
                        className={`rounded-full px-3 py-1 text-xs font-bold ${
                          d.has_feedback_loops
                            ? "bg-red-100 text-red-700"
                            : "bg-green-100 text-green-700"
                        }`}
                      >
                        {d.has_feedback_loops ? "Feedback Loops Detected" : "No Feedback Loops"}
                      </span>
                    </div>
                  </div>

                  {d.persistence_features.length > 0 && (
                    <div className="overflow-x-auto">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Persistence Features
                      </p>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-slate-200 text-left text-slate-500">
                            <th className="px-3 py-2 font-medium">Dimension</th>
                            <th className="px-3 py-2 font-medium">Birth</th>
                            <th className="px-3 py-2 font-medium">Death</th>
                            <th className="px-3 py-2 font-medium">Persistence</th>
                          </tr>
                        </thead>
                        <tbody>
                          {d.persistence_features.map((f, i) => (
                            <tr key={i} className="border-b border-slate-100">
                              <td className="px-3 py-2 text-slate-700">{f.dimension}</td>
                              <td className="px-3 py-2 text-slate-700">{f.birth.toFixed(4)}</td>
                              <td className="px-3 py-2 text-slate-700">
                                {Number.isFinite(f.death) ? f.death.toFixed(4) : "∞"}
                              </td>
                              <td className="px-3 py-2 text-slate-700">
                                {Number.isFinite(f.death)
                                  ? (f.death - f.birth).toFixed(4)
                                  : "∞"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 7 : Game Theory ──────────────────────────── */}
        {anyTriggered && (
          <Section
            title="Game Theory"
            tag="Nash Equilibrium"
            open={open.game}
            onToggle={() => toggle("game")}
            loading={game.loading}
            error={game.error}
            hasData={game.data !== null}
          >
            {game.data && (() => {
              const d = game.data;
              const ideal = d.ideal_clearances ?? {};
              const eff = d.effective_clearances ?? {};
              const red = d.clearance_reduction_pct ?? {};
              const drugNames = Object.keys(ideal);
              const drugRows = drugNames.map((name) => ({
                drug_name: name,
                ideal_clearance: ideal[name] ?? 0,
                effective_clearance: eff[name] ?? 0,
                clearance_reduction_pct: red[name] ?? 0,
              }));
              const ecm = d.enzyme_competition_matrix ?? {};
              const enzymeNames =
                drugNames.length > 0 && ecm[drugNames[0]] ?
                  Object.keys(ecm[drugNames[0]])
                : [];
              const competitionMatrix: number[][] = drugNames.map((dn) =>
                enzymeNames.map((en) => ecm[dn]?.[en] ?? 0),
              );
              return (
                <div className="space-y-5">
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    <div className="flex flex-col items-center justify-center rounded-lg border border-slate-200 bg-white p-4">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                        Price of Anarchy
                      </p>
                      <span
                        className={`mt-1 rounded-full px-3 py-1 text-lg font-bold ${
                          d.price_of_anarchy <= 1.05
                            ? "bg-green-100 text-green-700"
                            : d.price_of_anarchy <= 1.3
                              ? "bg-yellow-100 text-yellow-700"
                              : "bg-red-100 text-red-700"
                        }`}
                      >
                        {d.price_of_anarchy.toFixed(2)}x
                      </span>
                      <p className="mt-1 text-[10px] text-slate-400">
                        {d.price_of_anarchy <= 1.05
                          ? "Near-optimal"
                          : d.price_of_anarchy <= 1.3
                            ? "Moderate inefficiency"
                            : "Significant competition loss"}
                      </p>
                    </div>
                    <Stat label="Social Cost" value={d.social_cost.toFixed(4)} />
                  </div>

                  {drugRows.length > 0 && (
                    <div className="overflow-x-auto">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Clearance Comparison
                      </p>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-slate-200 text-left text-slate-500">
                            <th className="px-3 py-2 font-medium">Drug</th>
                            <th className="px-3 py-2 font-medium">Ideal CL</th>
                            <th className="px-3 py-2 font-medium">Effective CL</th>
                            <th className="px-3 py-2 font-medium">Reduction</th>
                          </tr>
                        </thead>
                        <tbody>
                          {drugRows.map((dr) => (
                            <tr key={dr.drug_name} className="border-b border-slate-100">
                              <td className="px-3 py-2 font-medium text-slate-700">
                                {dr.drug_name}
                              </td>
                              <td className="px-3 py-2 text-slate-600">
                                {dr.ideal_clearance.toFixed(3)}
                              </td>
                              <td className="px-3 py-2 text-slate-600">
                                {dr.effective_clearance.toFixed(3)}
                              </td>
                              <td className="px-3 py-2">
                                <span
                                  className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                                    dr.clearance_reduction_pct > 20
                                      ? "bg-red-100 text-red-700"
                                      : dr.clearance_reduction_pct > 10
                                        ? "bg-amber-100 text-amber-700"
                                        : "bg-green-100 text-green-700"
                                  }`}
                                >
                                  −{dr.clearance_reduction_pct.toFixed(1)}%
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {competitionMatrix.length > 0 && enzymeNames.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Enzyme Competition Matrix
                      </p>
                      <ColorGrid
                        matrix={competitionMatrix}
                        rowLabels={drugNames}
                        colLabels={enzymeNames}
                        hue="amber"
                      />
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}

        {/* ── Section 8 : Markov Chain ─────────────────────────── */}
        {anyTriggered && (
          <Section
            title="Markov Chain"
            tag="Stochastic Modelling"
            open={open.markov}
            onToggle={() => toggle("markov")}
            loading={markov.loading}
            error={markov.error}
            hasData={markov.data !== null}
          >
            {markov.data && (() => {
              const d = markov.data;
              const statEntries = Object.entries(d.stationary_distribution);
              const maxStat = Math.max(...statEntries.map(([, v]) => v), 0.01);
              const trajEntries = Object.entries(d.trajectory_summary);
              const maxTraj = Math.max(...trajEntries.map(([, v]) => v), 0.01);
              const fptStates = Object.keys(d.first_passage_times);

              return (
                <div className="space-y-5">
                  {statEntries.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Stationary Distribution
                      </p>
                      {statEntries.map(([state, prob]) => (
                        <HBar
                          key={state}
                          label={state}
                          value={prob}
                          max={maxStat}
                          format={(v) => `${(v * 100).toFixed(1)}%`}
                        />
                      ))}
                    </div>
                  )}

                  {fptStates.length > 0 && (
                    <div className="overflow-x-auto">
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        First Passage Times (weeks)
                      </p>
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="border-b border-slate-200 text-left text-slate-500">
                            <th className="px-3 py-2 font-medium">From \ To</th>
                            {fptStates.map((s) => (
                              <th key={s} className="px-3 py-2 font-medium">{s}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {fptStates.map((from) => (
                            <tr key={from} className="border-b border-slate-100">
                              <td className="px-3 py-2 font-medium text-slate-700">{from}</td>
                              {fptStates.map((to) => {
                                const val = d.first_passage_times[from]?.[to];
                                return (
                                  <td key={to} className="px-3 py-2 text-slate-600">
                                    {from === to
                                      ? "—"
                                      : val !== undefined
                                        ? Number.isFinite(val)
                                          ? val.toFixed(1)
                                          : "∞"
                                        : "—"}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {trajEntries.length > 0 && (
                    <div>
                      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                        Trajectory Summary
                      </p>
                      {trajEntries.map(([state, val]) => (
                        <HBar
                          key={state}
                          label={state}
                          value={val}
                          max={maxTraj}
                          format={(v) => v.toFixed(1)}
                        />
                      ))}
                    </div>
                  )}
                </div>
              );
            })()}
          </Section>
        )}
      </main>

      <DisclaimerFooter />
    </div>
  );
}
