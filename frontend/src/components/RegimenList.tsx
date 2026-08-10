import type { RegimenItem } from "../types";

interface Props {
  items: RegimenItem[];
  onRemove: (id: number) => void;
  onClear: () => void;
  onDosageChange: (id: number, dosage: string) => void;
}

export default function RegimenList({
  items,
  onRemove,
  onClear,
  onDosageChange,
}: Props) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
        No medications added yet. Use the search bar above to add medications.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-700">
          Current Regimen ({items.length})
        </h3>
        <button
          type="button"
          onClick={onClear}
          className="rounded px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50 transition"
        >
          Clear all
        </button>
      </div>

      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {items.map((item) => (
          <li
            key={item.id}
            className="flex items-center gap-3 px-4 py-3 text-sm"
          >
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-800 truncate">
                {item.generic_name}
              </p>
              <p className="text-xs text-slate-400 truncate">
                {item.drug_class}
                {item.brand_names.length > 0 &&
                  ` · ${item.brand_names.join(", ")}`}
              </p>
            </div>

            <input
              type="text"
              aria-label={`Dosage for ${item.generic_name}`}
              placeholder="e.g. 50 mg"
              value={item.dosage ?? ""}
              onChange={(e) => onDosageChange(item.id, e.target.value)}
              className="w-28 rounded border border-slate-200 px-2 py-1 text-xs
                         focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
            />

            <button
              type="button"
              aria-label={`Remove ${item.generic_name}`}
              onClick={() => onRemove(item.id)}
              className="flex-shrink-0 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-500 transition"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-4 w-4"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
