import { useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Trajectory = "linear" | "exponential";

interface DosePoint {
  day: number;
  dose: number;
}

function buildSchedule(
  startDose: number,
  durationDays: number,
  trajectory: Trajectory,
): DosePoint[] {
  if (!(startDose > 0) || !(durationDays > 0)) return [];

  const points: DosePoint[] = [];
  if (trajectory === "linear") {
    const step = startDose / durationDays;
    for (let d = 0; d <= durationDays; d++) {
      points.push({
        day: d,
        dose: Number(Math.max(0, startDose - step * d).toFixed(2)),
      });
    }
  } else {
    // Exponential: decay constant chosen so dose = 0.1 mg at final day.
    const k = Math.log(startDose / 0.1) / durationDays;
    for (let d = 0; d <= durationDays; d++) {
      const val = startDose * Math.exp(-k * d);
      points.push({ day: d, dose: Number((val < 0.2 ? 0 : val).toFixed(2)) });
    }
  }
  return points;
}

/**
 * Simple linear / exponential taper generator. Complements the
 * optimizer-driven taper in Simulator — this one is purely mathematical
 * (no PK/risk model) and lets clinicians sketch a reference schedule
 * quickly.
 */
export default function ManualTaperPlanner() {
  const [drug, setDrug] = useState("paroxetine");
  const [startDose, setStartDose] = useState(40);
  const [weeks, setWeeks] = useState(4);
  const [trajectory, setTrajectory] = useState<Trajectory>("linear");
  const [schedule, setSchedule] = useState<DosePoint[] | null>(null);

  const generate = () => {
    const s = buildSchedule(startDose, weeks * 7, trajectory);
    setSchedule(s.length ? s : null);
  };

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div>
        <h2 className="text-sm font-semibold text-slate-700">
          Manual Taper Planner
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Mathematical taper generator (linear or exponential). For a
          risk-aware, PK-informed schedule, use the Dose Taper Optimizer
          in the Simulator page instead.
        </p>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Medication
          <input
            type="text"
            value={drug}
            onChange={(e) => setDrug(e.target.value)}
            className="mt-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-indigo-400 focus:outline-none"
          />
        </label>
        <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Start dose (mg)
          <input
            type="number"
            min={0}
            value={startDose}
            onChange={(e) => setStartDose(Number(e.target.value))}
            className="mt-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-indigo-400 focus:outline-none"
          />
        </label>
        <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Duration (weeks)
          <input
            type="number"
            min={1}
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
            className="mt-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-indigo-400 focus:outline-none"
          />
        </label>
        <label className="flex flex-col text-[10px] font-semibold uppercase tracking-wide text-slate-500">
          Trajectory
          <select
            value={trajectory}
            onChange={(e) => setTrajectory(e.target.value as Trajectory)}
            className="mt-1 rounded-md border border-slate-300 bg-white px-2 py-1.5 text-sm text-slate-700 focus:border-indigo-400 focus:outline-none"
          >
            <option value="linear">Linear</option>
            <option value="exponential">Exponential (slower late)</option>
          </select>
        </label>
      </div>

      <button
        type="button"
        onClick={generate}
        disabled={startDose <= 0 || weeks <= 0}
        className="mt-4 rounded-md bg-indigo-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Generate Schedule
      </button>

      {schedule && (
        <div className="mt-5 space-y-5">
          <div className="flex items-center justify-between">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              {drug} — {trajectory} taper over {weeks} week{weeks === 1 ? "" : "s"}
            </p>
            <button
              type="button"
              onClick={() => window.print()}
              className="rounded-md border border-slate-200 px-3 py-1 text-[10px] font-medium text-slate-600 hover:bg-slate-50"
            >
              Print
            </button>
          </div>

          <div className="h-56 rounded-lg border border-slate-100 bg-slate-50 p-3">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={schedule} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorTaperDose" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `D${v}`}
                />
                <YAxis
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(v) => `${v}mg`}
                />
                <Tooltip
                  contentStyle={{ fontSize: 11, borderRadius: 8 }}
                  formatter={(v: number) => [`${v} mg`, "Target dose"]}
                  labelFormatter={(l) => `Day ${l}`}
                />
                <Area type="monotone" dataKey="dose" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#colorTaperDose)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
            {Array.from({ length: weeks }, (_, w) => {
              const weekSlice = schedule.slice(w * 7, (w + 1) * 7);
              return (
                <div
                  key={w}
                  className="overflow-hidden rounded-md border border-slate-200"
                >
                  <div className="bg-slate-100 px-3 py-1">
                    <span className="text-[9px] font-bold uppercase tracking-wide text-slate-500">
                      Week {w + 1}
                    </span>
                  </div>
                  <ul className="p-2 text-[11px]">
                    {weekSlice.map((p) => (
                      <li
                        key={p.day}
                        className="flex items-center justify-between"
                      >
                        <span className="text-slate-400">D{p.day}</span>
                        <span className="font-semibold text-slate-700">
                          {p.dose}mg
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}
