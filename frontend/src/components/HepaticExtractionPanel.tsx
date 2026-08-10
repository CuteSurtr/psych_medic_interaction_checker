import { useCallback, useState } from "react";
import type { SimulationSpec } from "../types";
import { apiUrl } from "../utils/api";

interface DrugResult {
  cl_intrinsic_l_per_h: number;
  cl_intrinsic_inhibited_l_per_h: number;
  cl_hepatic_l_per_h: number;
  cl_hepatic_inhibited_l_per_h: number;
  extraction_ratio: number;
  extraction_ratio_inhibited: number;
  first_pass_fraction: number;
  first_pass_fraction_inhibited: number;
  pathway_contributions_pct: Record<string, number>;
  classification: string;
  f_unbound: number;
}

interface HepaticResponse {
  q_hepatic_l_per_h: number;
  used_simulation_id: number | null;
  per_drug: Record<string, DrugResult>;
}

interface Props {
  medicationIds: number[];
  simulation: SimulationSpec | null;
}

function classBadge(c: string): string {
  if (c === "low") return "bg-green-100 text-green-700";
  if (c === "intermediate") return "bg-amber-100 text-amber-700";
  return "bg-red-100 text-red-700";
}

export default function HepaticExtractionPanel({
  medicationIds,
  simulation,
}: Props) {
  const [data, setData] = useState<HepaticResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(async () => {
    if (medicationIds.length === 0) return;
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch(apiUrl("/api/advanced/hepatic-extraction"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          medication_ids: medicationIds,
          simulation,
          q_hepatic_l_per_h: 81.0,
        }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = (await res.json()) as HepaticResponse;
      setData(json);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Hepatic extraction request failed",
      );
    } finally {
      setLoading(false);
    }
  }, [medicationIds, simulation]);

  const rows = data ? Object.entries(data.per_drug) : [];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            Hepatic Extraction (Well-Stirred PBPK)
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            CL<sub>h</sub> = Q<sub>h</sub>·f<sub>u</sub>·CL<sub>int</sub> /
            (Q<sub>h</sub> + f<sub>u</sub>·CL<sub>int</sub>) with
            competitive inhibition from co-prescribed drugs.
          </p>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={medicationIds.length === 0 || loading}
          className="shrink-0 rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Computing…" : "Compute CL_h"}
        </button>
      </div>

      {medicationIds.length === 0 && (
        <p className="mt-3 text-xs text-slate-400">
          Add medications to the regimen first.
        </p>
      )}

      {error && (
        <p className="mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {rows.length > 0 && (
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left text-slate-500">
                <th className="px-3 py-2 font-medium">Drug</th>
                <th className="px-3 py-2 font-medium">CL<sub>int</sub> (L/h)</th>
                <th className="px-3 py-2 font-medium">CL<sub>h</sub> (L/h)</th>
                <th className="px-3 py-2 font-medium">+ DDI (L/h)</th>
                <th className="px-3 py-2 font-medium">E<sub>h</sub></th>
                <th className="px-3 py-2 font-medium">F<sub>h</sub></th>
                <th className="px-3 py-2 font-medium">Class</th>
                <th className="px-3 py-2 font-medium">Top Enzyme</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([name, d]) => {
                const sortedPathways = Object.entries(d.pathway_contributions_pct).sort(
                  (a, b) => b[1] - a[1],
                );
                const top = sortedPathways[0];
                const ddiDrop =
                  d.cl_hepatic_l_per_h > 0
                    ? (1 - d.cl_hepatic_inhibited_l_per_h / d.cl_hepatic_l_per_h) * 100
                    : 0;
                return (
                  <tr key={name} className="border-b border-slate-100">
                    <td className="px-3 py-2 font-medium text-slate-700">{name}</td>
                    <td className="px-3 py-2 text-slate-600">
                      {d.cl_intrinsic_l_per_h.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {d.cl_hepatic_l_per_h.toFixed(2)}
                    </td>
                    <td className="px-3 py-2">
                      <span className="text-slate-700">
                        {d.cl_hepatic_inhibited_l_per_h.toFixed(2)}
                      </span>
                      {ddiDrop > 1 && (
                        <span className="ml-1 rounded bg-red-50 px-1 text-[10px] font-bold text-red-600">
                          −{ddiDrop.toFixed(0)}%
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {(d.extraction_ratio * 100).toFixed(0)}%
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {(d.first_pass_fraction * 100).toFixed(0)}%
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${classBadge(d.classification)}`}
                      >
                        {d.classification}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {top ? `${top[0]} (${top[1].toFixed(0)}%)` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
