import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface SchedulerMed {
  generic_name: string;
  drug_class: string;
  cns_depression_risk?: number | null;
}

interface Props {
  medications: SchedulerMed[];
}

/**
 * Splits a regimen into morning-dose and bedtime-dose groups using
 * pragmatic class rules and the `cns_depression_risk` attribute, then
 * draws a 24-hour activity curve to visualise when drug load peaks.
 *
 * Rules:
 *  - Bedtime:   benzodiazepines, Z-drugs, sedating TCAs/antipsychotics,
 *               or any drug with cns_depression_risk ≥ 2.
 *  - Morning:   stimulants, bupropion, SNRIs, modafinil / armodafinil.
 *  - Neutral:   default to morning for adherence.
 */
function bucket(med: SchedulerMed): "am" | "pm" {
  const name = med.generic_name.toLowerCase();
  const cls = med.drug_class.toLowerCase();
  const cns = med.cns_depression_risk ?? 0;

  if (cls.includes("benzodiazepine") || cls.includes("hypnotic")) return "pm";
  if (cns >= 2) return "pm";
  if (cls.includes("stimulant") || cls.includes("wakefulness")) return "am";
  if (["bupropion", "modafinil", "armodafinil", "atomoxetine", "viloxazine"].includes(name)) return "am";
  return "am";
}

export default function DosingScheduler({ medications }: Props) {
  if (!medications.length) return null;

  const amDrugs: string[] = [];
  const pmDrugs: string[] = [];
  for (const m of medications) {
    (bucket(m) === "am" ? amDrugs : pmDrugs).push(m.generic_name);
  }

  // 24-hour synthetic activity curve: AM dose at 08:00 peaking at 10:00,
  // PM dose at 21:00 peaking at 23:00. Used purely for visualisation.
  const data = Array.from({ length: 25 }, (_, hr) => {
    let am = 0;
    if (hr >= 8) am = Math.max(0, 100 - (hr - 10) * (hr - 10) * 1.5);
    let pm = 0;
    if (hr >= 21) pm = Math.max(0, 100 - (hr - 23) * (hr - 23) * 1.5);
    else if (hr < 8) pm = Math.max(0, 100 - (hr + 1) * (hr + 1) * 1.5);
    return {
      hour: hr,
      amLoad: amDrugs.length ? am : 0,
      pmLoad: pmDrugs.length ? pm : 0,
    };
  });

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            Time-of-Day Dosing Scheduler
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Buckets the current regimen into morning and bedtime doses based
            on sedation/activation profile, then visualises the 24-hour
            drug-load profile.
          </p>
        </div>
        <div className="flex gap-2">
          <span className="rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] font-bold text-amber-700">
            Activating (AM)
          </span>
          <span className="rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-[10px] font-bold text-indigo-700">
            Sedating (PM)
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-4">
        <div className="space-y-3 md:col-span-1">
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
            <p className="text-[10px] font-bold uppercase tracking-wide text-amber-700">
              Morning
            </p>
            <ul className="mt-1 space-y-0.5">
              {amDrugs.length === 0 ? (
                <li className="text-xs italic text-amber-600/60">—</li>
              ) : (
                amDrugs.map((d) => (
                  <li key={d} className="text-xs font-semibold text-amber-900">
                    • {d}
                  </li>
                ))
              )}
            </ul>
          </div>
          <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
            <p className="text-[10px] font-bold uppercase tracking-wide text-indigo-700">
              Bedtime
            </p>
            <ul className="mt-1 space-y-0.5">
              {pmDrugs.length === 0 ? (
                <li className="text-xs italic text-indigo-600/60">—</li>
              ) : (
                pmDrugs.map((d) => (
                  <li key={d} className="text-xs font-semibold text-indigo-900">
                    • {d}
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>

        <div className="h-48 rounded-lg border border-slate-100 bg-slate-50 p-3 md:col-span-3">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorAm" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="colorPm" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#818cf8" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#818cf8" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#e2e8f0" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="hour"
                tick={{ fill: "#94a3b8", fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(v) => (v === 12 ? "Noon" : v === 0 || v === 24 ? "Mid" : `${v}h`)}
              />
              <YAxis tick={false} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{ fontSize: 11, borderRadius: 8 }}
                labelFormatter={(v) => `${v}:00`}
                formatter={(val: number, name: string) => [
                  val > 5 ? "Active" : "Inactive",
                  name === "amLoad" ? "AM load" : "PM load",
                ]}
              />
              <ReferenceLine
                x={8}
                stroke="#fbbf24"
                strokeDasharray="3 3"
                label={{ position: "top", value: "Take AM", fill: "#d97706", fontSize: 10 }}
              />
              <ReferenceLine
                x={21}
                stroke="#818cf8"
                strokeDasharray="3 3"
                label={{ position: "top", value: "Take PM", fill: "#4f46e5", fontSize: 10 }}
              />
              <Area type="monotone" dataKey="amLoad" stroke="#fbbf24" strokeWidth={2.5} fill="url(#colorAm)" />
              <Area type="monotone" dataKey="pmLoad" stroke="#818cf8" strokeWidth={2.5} fill="url(#colorPm)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </section>
  );
}
