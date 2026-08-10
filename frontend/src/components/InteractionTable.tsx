import { useMemo, useState } from "react";
import type { InteractionRow } from "../types";
import { SEVERITY_COLORS } from "../utils/colorSchemes";

interface Props {
  interactions: InteractionRow[];
  onSelect: (row: InteractionRow) => void;
}

type SortKey = "drug_a_name" | "drug_b_name" | "severity" | "mechanism_type" | "clinical_effect";
type SortDir = "asc" | "desc";

const SEVERITY_RANK: Record<string, number> = {
  critical: 0,
  major: 1,
  moderate: 2,
  minor: 3,
  safe: 4,
};

export default function InteractionTable({ interactions, onSelect }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("severity");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const sorted = useMemo(() => {
    const copy = [...interactions];
    copy.sort((a, b) => {
      let cmp: number;
      if (sortKey === "severity") {
        cmp =
          (SEVERITY_RANK[a.severity.toLowerCase()] ?? 50) -
          (SEVERITY_RANK[b.severity.toLowerCase()] ?? 50);
      } else {
        cmp = a[sortKey].localeCompare(b[sortKey]);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return copy;
  }, [interactions, sortKey, sortDir]);

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  };

  const columns: { key: SortKey; label: string }[] = [
    { key: "drug_a_name", label: "Drug A" },
    { key: "drug_b_name", label: "Drug B" },
    { key: "severity", label: "Severity" },
    { key: "mechanism_type", label: "Mechanism" },
    { key: "clinical_effect", label: "Clinical Effect" },
  ];

  if (interactions.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
        No interactions found.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-xs font-semibold text-slate-500">
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className="cursor-pointer select-none whitespace-nowrap px-4 py-2.5 hover:text-slate-700 transition"
                onClick={() => toggleSort(col.key)}
              >
                {col.label}
                {sortKey === col.key && (
                  <span className="ml-1">{sortDir === "asc" ? "▲" : "▼"}</span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {sorted.map((row, idx) => {
            const sevColor =
              SEVERITY_COLORS[row.severity.toLowerCase()] ??
              SEVERITY_COLORS.minor;
            return (
              <tr
                key={`${row.drug_a_id}-${row.drug_b_id}-${idx}`}
                onClick={() => onSelect(row)}
                className="cursor-pointer hover:bg-slate-50 transition"
              >
                <td className="px-4 py-2.5 font-medium text-slate-700">
                  {row.drug_a_name}
                </td>
                <td className="px-4 py-2.5 font-medium text-slate-700">
                  {row.drug_b_name}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold text-white"
                    style={{ backgroundColor: sevColor }}
                  >
                    {row.severity}
                  </span>
                </td>
                <td className="px-4 py-2.5 text-slate-600">
                  {row.mechanism_type}
                </td>
                <td className="max-w-xs truncate px-4 py-2.5 text-slate-600">
                  {row.clinical_effect}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
