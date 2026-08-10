interface Props {
  cyp2d6: string;
  cyp2c19: string;
  onChange: (cyp2d6: string, cyp2c19: string) => void;
}

const PHENOTYPE_OPTIONS = ["normal", "poor", "intermediate", "ultra-rapid"];

export default function PhenotypeSelector({ cyp2d6, cyp2c19, onChange }: Props) {
  return (
    <div className="flex flex-wrap gap-4">
      <div>
        <label
          htmlFor="pheno-cyp2d6"
          className="block text-xs font-medium text-slate-600 mb-1"
        >
          CYP2D6 Phenotype
        </label>
        <select
          id="pheno-cyp2d6"
          value={cyp2d6}
          onChange={(e) => onChange(e.target.value, cyp2c19)}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm
                     focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
        >
          {PHENOTYPE_OPTIONS.map((o) => (
            <option key={o} value={o}>
              {o.charAt(0).toUpperCase() + o.slice(1)}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label
          htmlFor="pheno-cyp2c19"
          className="block text-xs font-medium text-slate-600 mb-1"
        >
          CYP2C19 Phenotype
        </label>
        <select
          id="pheno-cyp2c19"
          value={cyp2c19}
          onChange={(e) => onChange(cyp2d6, e.target.value)}
          className="rounded border border-slate-300 px-3 py-1.5 text-sm
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
  );
}
