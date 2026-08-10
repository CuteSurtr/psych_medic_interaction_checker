import type { PatientContext } from "../types";

interface Props {
  value: PatientContext;
  onChange: (v: PatientContext) => void;
}

const PHENOTYPE_OPTIONS = ["normal", "poor", "intermediate", "ultra-rapid"];

export default function PatientContextPanel({ value, onChange }: Props) {
  const update = <K extends keyof PatientContext>(
    key: K,
    val: PatientContext[K]
  ) => {
    onChange({ ...value, [key]: val });
  };

  return (
    <fieldset className="rounded-lg border border-slate-200 bg-white p-5">
      <legend className="px-2 text-sm font-semibold text-slate-700">
        Patient Context
      </legend>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Age */}
        <div>
          <label
            htmlFor="pc-age"
            className="block text-xs font-medium text-slate-600 mb-1"
          >
            Age
          </label>
          <input
            id="pc-age"
            type="number"
            min={0}
            max={120}
            value={value.age}
            onChange={(e) =>
              update("age", e.target.value === "" ? "" : Number(e.target.value))
            }
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm
                       focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
          />
        </div>

        {/* Weight */}
        <div>
          <label
            htmlFor="pc-weight"
            className="block text-xs font-medium text-slate-600 mb-1"
          >
            Weight (kg)
          </label>
          <input
            id="pc-weight"
            type="number"
            min={1}
            max={300}
            value={value.weight_kg}
            onChange={(e) => update("weight_kg", e.target.value === "" ? "" : Number(e.target.value))}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm
                       focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
          />
        </div>

        {/* eGFR */}
        <div>
          <label
            htmlFor="pc-egfr"
            className="block text-xs font-medium text-slate-600 mb-1"
          >
            eGFR (mL/min)
          </label>
          <input
            id="pc-egfr"
            type="number"
            min={0}
            max={200}
            value={value.egfr}
            onChange={(e) =>
              update("egfr", e.target.value === "" ? "" : Number(e.target.value))
            }
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm
                       focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
          />
        </div>

        {/* Hepatic Impairment */}
        <div>
          <label
            htmlFor="pc-hepatic"
            className="block text-xs font-medium text-slate-600 mb-1"
          >
            Hepatic Impairment
          </label>
          <select
            id="pc-hepatic"
            value={value.hepatic_impairment}
            onChange={(e) =>
              update(
                "hepatic_impairment",
                e.target.value as PatientContext["hepatic_impairment"]
              )
            }
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm
                       focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
          >
            <option value="none">None</option>
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
          </select>
        </div>

        {/* Smoking */}
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={value.smoking_status}
            onChange={(e) => update("smoking_status", e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-indigo-600
                       focus:ring-indigo-500"
          />
          Smoking
        </label>

        {/* Pregnancy */}
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={value.pregnancy_status}
            onChange={(e) => update("pregnancy_status", e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-indigo-600
                       focus:ring-indigo-500"
          />
          Pregnancy
        </label>

        {/* CYP2D6 */}
        <div>
          <label
            htmlFor="pc-cyp2d6"
            className="block text-xs font-medium text-slate-600 mb-1"
          >
            CYP2D6 Phenotype
          </label>
          <select
            id="pc-cyp2d6"
            value={value.cyp2d6_phenotype}
            onChange={(e) => update("cyp2d6_phenotype", e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm
                       focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
          >
            {PHENOTYPE_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {o.charAt(0).toUpperCase() + o.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* CYP2C19 */}
        <div>
          <label
            htmlFor="pc-cyp2c19"
            className="block text-xs font-medium text-slate-600 mb-1"
          >
            CYP2C19 Phenotype
          </label>
          <select
            id="pc-cyp2c19"
            value={value.cyp2c19_phenotype}
            onChange={(e) => update("cyp2c19_phenotype", e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-1.5 text-sm
                       focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
          >
            {PHENOTYPE_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {o.charAt(0).toUpperCase() + o.slice(1)}
              </option>
            ))}
          </select>
        </div>
      </div>
    </fieldset>
  );
}
