import type { SimulationResult } from "../types";

interface Props {
  info: SimulationResult["steady_state_info"] | null;
}

export default function SteadyStateSummary({ info }: Props) {
  if (!info || info.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
        Run a simulation to view steady-state pharmacokinetic data.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500">
          <tr>
            <th className="px-4 py-2.5">Drug</th>
            <th className="px-4 py-2.5">Trough (ng/mL)</th>
            <th className="px-4 py-2.5">Peak (ng/mL)</th>
            <th className="px-4 py-2.5">Time to Steady State (days)</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {info.map((row) => (
            <tr key={row.drug_name} className="hover:bg-slate-50 transition">
              <td className="px-4 py-2.5 font-medium text-slate-700">
                {row.drug_name}
              </td>
              <td className="px-4 py-2.5 tabular-nums text-slate-600">
                {row.trough_ng_ml.toFixed(1)}
              </td>
              <td className="px-4 py-2.5 tabular-nums text-slate-600">
                {row.peak_ng_ml.toFixed(1)}
              </td>
              <td className="px-4 py-2.5 tabular-nums text-slate-600">
                {row.time_to_steady_state_days !== null ? row.time_to_steady_state_days.toFixed(1) : "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
