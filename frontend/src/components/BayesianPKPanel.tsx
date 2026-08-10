import { useCallback, useState } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { apiUrl } from "../utils/api";

interface Obs {
  time_h: number;
  concentration_ng_ml: number;
}

interface Dose {
  time_h: number;
  dose_mg: number;
}

interface BayesianResponse {
  map_cl_l_per_h: number;
  map_vd_l: number;
  ci95_cl_l_per_h: [number, number];
  ci95_vd_l: [number, number];
  n_observations: number;
  converged: boolean;
  prediction_time_hours: number[];
  prediction_ng_ml: number[];
  prediction_ci_low_ng_ml: number[];
  prediction_ci_high_ng_ml: number[];
}

export default function BayesianPKPanel() {
  const [obs, setObs] = useState<Obs[]>([
    { time_h: 4, concentration_ng_ml: 100 },
    { time_h: 12, concentration_ng_ml: 60 },
    { time_h: 24, concentration_ng_ml: 25 },
  ]);
  const [doses, setDoses] = useState<Dose[]>([{ time_h: 0, dose_mg: 100 }]);
  const [muCL, setMuCL] = useState(5);
  const [sigmaCL, setSigmaCL] = useState(0.3);
  const [muVd, setMuVd] = useState(50);
  const [sigmaVd, setSigmaVd] = useState(0.3);
  const [ka, setKa] = useState(1.0);
  const [f, setF] = useState(0.8);
  const [sigmaObs, setSigmaObs] = useState(0.2);
  const [data, setData] = useState<BayesianResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch(apiUrl("/api/advanced/bayesian-pk"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          observations: obs,
          doses: doses,
          mu_log_cl: Math.log(muCL),
          sigma_log_cl: sigmaCL,
          mu_log_vd: Math.log(muVd),
          sigma_log_vd: sigmaVd,
          ka_per_h: ka,
          bioavailability: f,
          sigma_obs: sigmaObs,
        }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = (await res.json()) as BayesianResponse;
      setData(json);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Bayesian PK request failed",
      );
    } finally {
      setLoading(false);
    }
  }, [obs, doses, muCL, sigmaCL, muVd, sigmaVd, ka, f, sigmaObs]);

  const chartData = data
    ? data.prediction_time_hours.map((h, i) => ({
        hour: h,
        predicted: data.prediction_ng_ml[i],
        range: [
          data.prediction_ci_low_ng_ml[i],
          data.prediction_ci_high_ng_ml[i],
        ] as [number, number],
        observed: obs.find((o) => Math.abs(o.time_h - h) < 0.1)?.concentration_ng_ml ?? null,
      }))
    : [];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            Bayesian Individual PK (MIPD)
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            MAP + Laplace posterior on (CL, V<sub>d</sub>) from therapeutic
            drug monitoring observations. Log-normal population prior.
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
            Population Prior
          </p>
          <div className="grid grid-cols-2 gap-2 text-xs">
            <NumInput label="μ CL (L/h)" value={muCL} step={0.5} onChange={setMuCL} />
            <NumInput label="σ log CL" value={sigmaCL} step={0.05} onChange={setSigmaCL} />
            <NumInput label="μ Vd (L)" value={muVd} step={5} onChange={setMuVd} />
            <NumInput label="σ log Vd" value={sigmaVd} step={0.05} onChange={setSigmaVd} />
            <NumInput label="ka (h⁻¹)" value={ka} step={0.1} onChange={setKa} />
            <NumInput label="F" value={f} step={0.05} onChange={setF} />
            <NumInput label="σ obs" value={sigmaObs} step={0.05} onChange={setSigmaObs} />
          </div>
        </div>

        <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Doses
            </p>
            <button
              type="button"
              onClick={() => setDoses([...doses, { time_h: 0, dose_mg: 100 }])}
              className="rounded-md bg-white px-2 py-0.5 text-[10px] font-medium text-indigo-600 hover:bg-indigo-50"
            >
              + Add
            </button>
          </div>
          {doses.map((d, i) => (
            <div key={i} className="flex gap-2 text-xs">
              <NumInput
                label="t (h)"
                value={d.time_h}
                onChange={(v) =>
                  setDoses(doses.map((x, j) => (j === i ? { ...x, time_h: v } : x)))
                }
              />
              <NumInput
                label="mg"
                value={d.dose_mg}
                onChange={(v) =>
                  setDoses(doses.map((x, j) => (j === i ? { ...x, dose_mg: v } : x)))
                }
              />
              <button
                type="button"
                onClick={() => setDoses(doses.filter((_, j) => j !== i))}
                className="self-end text-slate-400 hover:text-red-500"
              >
                ✕
              </button>
            </div>
          ))}

          <div className="flex items-center justify-between pt-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              TDM Observations
            </p>
            <button
              type="button"
              onClick={() => setObs([...obs, { time_h: 0, concentration_ng_ml: 0 }])}
              className="rounded-md bg-white px-2 py-0.5 text-[10px] font-medium text-indigo-600 hover:bg-indigo-50"
            >
              + Add
            </button>
          </div>
          {obs.map((o, i) => (
            <div key={i} className="flex gap-2 text-xs">
              <NumInput
                label="t (h)"
                value={o.time_h}
                onChange={(v) =>
                  setObs(obs.map((x, j) => (j === i ? { ...x, time_h: v } : x)))
                }
              />
              <NumInput
                label="ng/mL"
                value={o.concentration_ng_ml}
                onChange={(v) =>
                  setObs(
                    obs.map((x, j) => (j === i ? { ...x, concentration_ng_ml: v } : x)),
                  )
                }
              />
              <button
                type="button"
                onClick={() => setObs(obs.filter((_, j) => j !== i))}
                className="self-end text-slate-400 hover:text-red-500"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>

      <button
        type="button"
        onClick={run}
        disabled={loading || obs.length === 0 || doses.length === 0}
        className="mt-4 rounded-md bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {loading ? "Estimating…" : "Estimate Posterior"}
      </button>

      {error && (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {data && (
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat
              label="MAP CL"
              value={`${data.map_cl_l_per_h.toFixed(2)} L/h`}
              sub={`95% CI ${data.ci95_cl_l_per_h[0].toFixed(2)}–${data.ci95_cl_l_per_h[1].toFixed(2)}`}
            />
            <Stat
              label="MAP Vd"
              value={`${data.map_vd_l.toFixed(1)} L`}
              sub={`95% CI ${data.ci95_vd_l[0].toFixed(1)}–${data.ci95_vd_l[1].toFixed(1)}`}
            />
            <Stat label="Observations" value={String(data.n_observations)} />
            <Stat
              label="Convergence"
              value={data.converged ? "yes" : "no"}
            />
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={chartData}
                margin={{ top: 10, right: 20, left: 0, bottom: 20 }}
              >
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" />
                <XAxis
                  dataKey="hour"
                  tick={{ fontSize: 11 }}
                  label={{ value: "Hours", position: "insideBottom", offset: -5, style: { fontSize: 11, fill: "#64748b" } }}
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  label={{ value: "ng/mL", angle: -90, position: "insideLeft", style: { fontSize: 11, fill: "#64748b" } }}
                />
                <Tooltip contentStyle={{ fontSize: 11 }} formatter={(v: number) => v?.toFixed?.(2) ?? v} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area
                  type="monotone"
                  dataKey="range"
                  name="95% CrI"
                  fill="#6366f1"
                  fillOpacity={0.2}
                  stroke="transparent"
                />
                <Line
                  type="monotone"
                  dataKey="predicted"
                  name="Posterior mean"
                  stroke="#4f46e5"
                  dot={false}
                />
                <Scatter dataKey="observed" name="TDM" fill="#ef4444" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </section>
  );
}

function NumInput({
  label,
  value,
  step,
  onChange,
}: {
  label: string;
  value: number;
  step?: number;
  onChange: (v: number) => void;
}) {
  return (
    <label className="flex flex-col text-[10px] font-medium text-slate-500">
      {label}
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-0.5 rounded border border-slate-300 bg-white px-2 py-1 text-xs text-slate-700 focus:border-indigo-400 focus:outline-none"
      />
    </label>
  );
}

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-bold text-slate-800">{value}</p>
      {sub && <p className="mt-0.5 text-[10px] text-slate-500">{sub}</p>}
    </div>
  );
}
