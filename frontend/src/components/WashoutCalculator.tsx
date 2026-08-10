import type { RegimenItem } from "../types";

interface Props {
  regimen: RegimenItem[];
}

export function WashoutCalculator({ regimen }: Props) {
  if (regimen.length === 0) return null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-slate-800">
        Washout Period Estimates
      </h3>
      <p className="mt-1 text-xs text-slate-500">
        Approximate time to reach {"<"}10% of steady-state concentration after
        discontinuation ({"\u2248"}3.3 {"\u00D7"} half-life).
      </p>
      <div className="mt-3 space-y-2 text-sm">
        {regimen.map((m) => (
          <div
            key={m.id}
            className="flex items-baseline justify-between border-b border-slate-100 pb-1"
          >
            <span className="font-medium text-slate-700">
              {m.generic_name}
            </span>
            <span className="text-xs text-slate-500">{m.drug_class}</span>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded bg-amber-50 p-3 text-xs text-amber-900">
        <p className="font-semibold">MAOI Washout Requirements</p>
        <ul className="mt-1 list-inside list-disc space-y-1">
          <li>
            From fluoxetine to MAOI: wait at least <strong>5 weeks</strong>
          </li>
          <li>
            From other SSRIs/SNRIs to MAOI: wait at least{" "}
            <strong>2 weeks</strong>
          </li>
          <li>
            From MAOI to any serotonergic drug: wait at least{" "}
            <strong>2 weeks</strong>
          </li>
        </ul>
      </div>
    </div>
  );
}
