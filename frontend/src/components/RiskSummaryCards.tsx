import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RiskSummary } from "../types";
import { SEVERITY_COLORS } from "../utils/colorSchemes";

interface Props {
  summary: RiskSummary | null;
}

export default function RiskSummaryCards({ summary }: Props) {
  if (!summary) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
        Add at least two medications to see risk analysis.
      </div>
    );
  }

  const chartData = Object.entries(summary.counts_by_severity).map(
    ([severity, count]) => ({ severity, count })
  );

  const pills: { label: string; value: string | number; color: string }[] = [
    {
      label: "Serotonin",
      value: summary.serotonin_risk,
      color: riskColor(summary.serotonin_risk),
    },
    {
      label: "QTc",
      value: summary.qtc_risk,
      color: riskColor(summary.qtc_risk),
    },
    {
      label: "Anticholinergic",
      value: summary.anticholinergic_burden,
      color: burdenColor(summary.anticholinergic_burden),
    },
    {
      label: "CNS Depression",
      value: summary.cns_depression_risk,
      color: riskColor(summary.cns_depression_risk),
    },
  ];

  return (
    <div className="space-y-4">
      {/* Top risk alert */}
      {summary.top_risk && (
        <div
          className={`rounded-lg px-4 py-3 text-sm font-medium ${
            summary.top_risk.severity.toLowerCase() === "critical"
              ? "border border-red-300 bg-red-50 text-red-800"
              : "border border-amber-300 bg-amber-50 text-amber-800"
          }`}
        >
          <span className="font-bold">Top Risk:</span>{" "}
          {summary.top_risk.drug_a_name} + {summary.top_risk.drug_b_name} —{" "}
          {summary.top_risk.clinical_effect}
        </div>
      )}

      {/* Risk pills */}
      <div className="flex flex-wrap gap-2">
        {pills.map((p) => (
          <span
            key={p.label}
            className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium"
            style={{
              borderColor: p.color,
              color: p.color,
              backgroundColor: `${p.color}10`,
            }}
          >
            {p.label}: {p.value}
          </span>
        ))}
      </div>

      {/* Severity bar chart */}
      {chartData.length > 0 && (
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              margin={{ top: 8, right: 12, left: 0, bottom: 4 }}
            >
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="severity"
                tick={{ fontSize: 11 }}
                tickLine={false}
              />
              <YAxis
                allowDecimals={false}
                tick={{ fontSize: 11 }}
                tickLine={false}
                width={30}
              />
              <Tooltip
                contentStyle={{ fontSize: 12, borderRadius: 8 }}
                cursor={{ fill: "rgba(0,0,0,0.04)" }}
              />
              <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                {chartData.map((entry) => (
                  <Cell
                    key={entry.severity}
                    fill={
                      SEVERITY_COLORS[entry.severity.toLowerCase()] ??
                      SEVERITY_COLORS.minor
                    }
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Contextual notes */}
      {summary.contextual_notes.length > 0 && (
        <ul className="space-y-1 text-xs text-slate-600">
          {summary.contextual_notes.map((note, i) => (
            <li key={i} className="flex items-start gap-1.5">
              <span className="mt-0.5 block h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400" />
              {note}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function riskColor(level: string): string {
  switch (level.toLowerCase()) {
    case "critical":
      return SEVERITY_COLORS.critical;
    case "high":
      return SEVERITY_COLORS.major;
    case "moderate":
      return SEVERITY_COLORS.moderate;
    case "low":
      return SEVERITY_COLORS.safe;
    default:
      return SEVERITY_COLORS.minor;
  }
}

function burdenColor(burden: number): string {
  if (burden >= 3) return SEVERITY_COLORS.critical;
  if (burden >= 2) return SEVERITY_COLORS.moderate;
  return SEVERITY_COLORS.safe;
}
