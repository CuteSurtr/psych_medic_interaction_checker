import { useCallback, useState } from "react";
import type { SimulationSpec } from "../types";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiUrl } from "../utils/api";

interface DrugResult {
  surface_ng_ml: number[];
  mean_ng_ml: number[];
  deep_ng_ml: number[];
  plasma_unbound_ng_ml: number[];
  time_to_80pct_h: number | null;
  p_eff_cm_per_h: number;
  f_unbound: number;
}

interface PDEResponse {
  time_hours: number[];
  x_cm: number[];
  per_drug: Record<string, DrugResult>;
}

interface Props {
  simulation: SimulationSpec | null;
}

export default function TissueDistributionPanel({ simulation }: Props) {
  const [data, setData] = useState<PDEResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeDrug, setActiveDrug] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (simulation === null) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch(apiUrl("/api/advanced/tissue-pde"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ simulation }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = (await res.json()) as PDEResponse;
      setData(json);
      const first = Object.keys(json.per_drug)[0] ?? null;
      setActiveDrug(first);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Tissue PDE request failed");
    } finally {
      setLoading(false);
    }
  }, [simulation]);

  const drugNames = data ? Object.keys(data.per_drug) : [];
  const drug = activeDrug && data ? data.per_drug[activeDrug] : null;

  const chartData =
    drug && data
      ? data.time_hours.map((h, i) => ({
          day: h / 24,
          plasmaUnbound: drug.plasma_unbound_ng_ml[i],
          surface: drug.surface_ng_ml[i],
          mean: drug.mean_ng_ml[i],
          deep: drug.deep_ng_ml[i],
        }))
      : [];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            CNS Tissue Distribution (Reaction-Diffusion PDE)
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Solves ∂C/∂t = D·∂²C/∂x² − k<sub>e</sub>·C through the BBB with a Robin
            boundary condition.
          </p>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={simulation === null || loading}
          className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Solving…" : "Solve PDE"}
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

          {drug && (
            <div className="mt-4 space-y-4">
              <div className="grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
                <Stat
                  label="P_eff"
                  value={`${drug.p_eff_cm_per_h.toFixed(3)} cm/h`}
                />
                <Stat
                  label="f_unbound"
                  value={(drug.f_unbound * 100).toFixed(1) + "%"}
                />
                <Stat
                  label="Time to 80% equilibrium"
                  value={
                    drug.time_to_80pct_h === null
                      ? "not reached"
                      : `${(drug.time_to_80pct_h / 24).toFixed(1)} d`
                  }
                />
                <Stat
                  label="CNS lag"
                  value={
                    drug.time_to_80pct_h === null
                      ? "very slow"
                      : drug.time_to_80pct_h < 24
                        ? "rapid"
                        : drug.time_to_80pct_h < 168
                          ? "days"
                          : "weeks"
                  }
                />
              </div>

              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 20 }}>
                    <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                    <XAxis
                      dataKey="day"
                      tick={{ fontSize: 11 }}
                      label={{ value: "Days", position: "insideBottom", offset: -5, style: { fontSize: 11, fill: "#64748b" } }}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      label={{ value: "ng/mL", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: "#64748b" } }}
                    />
                    <Tooltip
                      contentStyle={{ fontSize: 11 }}
                      formatter={(v: number) => v.toFixed(3)}
                      labelFormatter={(d: number) => `Day ${d.toFixed(2)}`}
                    />
                    <Legend wrapperStyle={{ fontSize: 11 }} />
                    <Line
                      type="monotone"
                      dataKey="plasmaUnbound"
                      name="Plasma (unbound)"
                      stroke="#64748b"
                      strokeDasharray="4 2"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="surface"
                      name="Brain surface"
                      stroke="#6366f1"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="mean"
                      name="Brain mean"
                      stroke="#0ea5e9"
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="deep"
                      name="Deep tissue"
                      stroke="#ef4444"
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-bold text-slate-800">{value}</p>
    </div>
  );
}
