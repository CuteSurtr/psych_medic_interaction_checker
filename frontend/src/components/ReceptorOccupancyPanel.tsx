import { useCallback, useState } from "react";
import type { SimulationSpec } from "../types";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ReferenceArea,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiUrl } from "../utils/api";

interface Trajectory {
  target: string;
  k_d_nm: number;
  mechanism: string;
  occupancy_pct: number[];
  peak_occupancy_pct: number;
  trough_occupancy_pct: number;
  time_to_threshold_h: number | null;
  steady_state_label: string;
}

interface DrugResult {
  mw_g_per_mol: number;
  has_profile: boolean;
  trajectories: Trajectory[];
}

interface OccupancyResponse {
  time_hours: number[];
  per_drug: Record<string, DrugResult>;
}

interface Props {
  simulation: SimulationSpec | null;
}

function labelColor(label: string): string {
  if (label === "therapeutic") return "#22c55e";
  if (label === "EPS / side-effect risk") return "#ef4444";
  if (label === "supratherapeutic") return "#f59e0b";
  return "#94a3b8";
}

export default function ReceptorOccupancyPanel({ simulation }: Props) {
  const [data, setData] = useState<OccupancyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeDrug, setActiveDrug] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (simulation === null) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch(apiUrl("/api/advanced/receptor-occupancy"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ simulation, use_f_unbound: true }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = (await res.json()) as OccupancyResponse;
      setData(json);
      const first = Object.keys(json.per_drug)[0] ?? null;
      setActiveDrug(first);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Occupancy request failed");
    } finally {
      setLoading(false);
    }
  }, [simulation]);

  const drugNames = data ? Object.keys(data.per_drug) : [];
  const drug = activeDrug && data ? data.per_drug[activeDrug] : null;

  const peakData =
    drug?.trajectories.map((t) => ({
      target: t.target,
      peak: t.peak_occupancy_pct,
      label: t.steady_state_label,
    })) ?? [];

  const timeSeriesData =
    drug && data
      ? data.time_hours.map((h, i) => {
          const point: Record<string, number> = { day: h / 24 };
          for (const t of drug.trajectories) {
            point[t.target] = t.occupancy_pct[i];
          }
          return point;
        })
      : [];

  const palette = [
    "#6366f1",
    "#0ea5e9",
    "#22c55e",
    "#ef4444",
    "#f59e0b",
    "#a855f7",
    "#14b8a6",
    "#ec4899",
  ];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            Receptor Occupancy (PD Link)
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Hill-1 fractional occupancy at SERT, D2, 5-HT2A, etc. using
            published K<sub>d</sub> values; plasma scaled by f<sub>u</sub>.
          </p>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={simulation === null || loading}
          className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Computing…" : "Compute Occupancy"}
        </button>
      </div>

      {simulation === null && (
        <p className="mt-3 text-xs text-slate-400">
          Run a PK simulation first.
        </p>
      )}

      {error && (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {data && drugNames.length > 0 && (
        <>
          <div className="mt-4 flex flex-wrap gap-2">
            {drugNames.map((name) => (
              <button
                key={name}
                type="button"
                onClick={() => setActiveDrug(name)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition ${
                  activeDrug === name
                    ? "bg-indigo-600 text-white"
                    : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                }`}
              >
                {name}
              </button>
            ))}
          </div>

          {drug && drug.trajectories.length === 0 && (
            <p className="mt-4 text-xs text-amber-600">
              No binding profile on file for {activeDrug}.
            </p>
          )}

          {drug && drug.trajectories.length > 0 && (
            <div className="mt-4 space-y-5">
              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Peak Occupancy by Target
                </p>
                <div className="h-56 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={peakData} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                      <XAxis dataKey="target" tick={{ fontSize: 11 }} />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                      <Tooltip
                        contentStyle={{ fontSize: 11 }}
                        formatter={(v: number, _n: string, payload: { payload?: { label?: string } }) => {
                          const lbl = payload?.payload?.label ?? "";
                          return [`${v.toFixed(1)}%`, lbl];
                        }}
                      />
                      <Bar dataKey="peak" name="Peak Occupancy">
                        {peakData.map((d, i) => (
                          <Cell key={i} fill={labelColor(d.label)} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div>
                <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  Occupancy over Time
                </p>
                <div className="h-60 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={timeSeriesData} margin={{ top: 5, right: 20, left: 0, bottom: 20 }}>
                      <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                      <XAxis
                        dataKey="day"
                        tick={{ fontSize: 11 }}
                        label={{ value: "Days", position: "insideBottom", offset: -5, style: { fontSize: 11, fill: "#64748b" } }}
                      />
                      <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} unit="%" />
                      <Tooltip
                        contentStyle={{ fontSize: 11 }}
                        formatter={(v: number) => `${v.toFixed(1)}%`}
                      />
                      <Legend wrapperStyle={{ fontSize: 11 }} />
                      <ReferenceArea y1={60} y2={80} fill="#22c55e" fillOpacity={0.05} />
                      {drug.trajectories.map((t, i) => (
                        <Line
                          key={t.target}
                          type="monotone"
                          dataKey={t.target}
                          stroke={palette[i % palette.length]}
                          dot={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-200 text-left text-slate-500">
                      <th className="px-3 py-2 font-medium">Target</th>
                      <th className="px-3 py-2 font-medium">K<sub>d</sub> (nM)</th>
                      <th className="px-3 py-2 font-medium">Mechanism</th>
                      <th className="px-3 py-2 font-medium">Peak %</th>
                      <th className="px-3 py-2 font-medium">Trough %</th>
                      <th className="px-3 py-2 font-medium">Classification</th>
                    </tr>
                  </thead>
                  <tbody>
                    {drug.trajectories.map((t) => (
                      <tr key={t.target} className="border-b border-slate-100">
                        <td className="px-3 py-2 font-medium text-slate-700">{t.target}</td>
                        <td className="px-3 py-2 text-slate-600">{t.k_d_nm.toFixed(2)}</td>
                        <td className="px-3 py-2 text-slate-600">{t.mechanism}</td>
                        <td className="px-3 py-2 text-slate-700">{t.peak_occupancy_pct.toFixed(1)}</td>
                        <td className="px-3 py-2 text-slate-700">{t.trough_occupancy_pct.toFixed(1)}</td>
                        <td className="px-3 py-2">
                          <span
                            className="rounded-full px-2 py-0.5 text-[10px] font-bold text-white"
                            style={{ backgroundColor: labelColor(t.steady_state_label) }}
                          >
                            {t.steady_state_label}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
