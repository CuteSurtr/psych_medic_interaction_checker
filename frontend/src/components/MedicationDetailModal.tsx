import { useEffect, useRef, useState } from "react";
import type { MedicationDetail } from "../types";
import { apiUrl } from "../utils/api";

interface Props {
  medId: number | null;
  onClose: () => void;
}

export default function MedicationDetailModal({ medId, onClose }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const [med, setMed] = useState<MedicationDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (medId === null) {
      setMed(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(apiUrl(`/api/medications/${medId}`))
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: MedicationDetail) => {
        if (!cancelled) setMed(data);
      })
      .catch((err) => {
        if (!cancelled) setError(String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [medId]);

  const isOpen = medId !== null;

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (isOpen && !el.open) el.showModal();
    else if (!isOpen && el.open) el.close();
  }, [isOpen]);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const handler = () => onClose();
    el.addEventListener("close", handler);
    return () => el.removeEventListener("close", handler);
  }, [onClose]);

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-label="Medication details"
      className="m-auto w-full max-w-lg rounded-xl border border-slate-200 bg-white p-0 shadow-2xl backdrop:bg-black/40"
    >
      <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4">
        <h2 className="text-base font-semibold text-slate-800">
          {med?.generic_name ?? "Medication Details"}
        </h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="rounded p-1 text-slate-400 hover:text-slate-600 transition"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5"
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
      </div>

      <div className="max-h-[70vh] overflow-y-auto px-6 py-5 text-sm text-slate-700">
        {loading && (
          <p className="py-8 text-center text-slate-400">Loading…</p>
        )}
        {error && (
          <p className="py-8 text-center text-red-500">{error}</p>
        )}
        {med && !loading && (
          <div className="space-y-4">
            <Row label="Generic Name" value={med.generic_name} />
            <Row
              label="Brand Names"
              value={
                med.brand_names.length > 0
                  ? med.brand_names.join(", ")
                  : "—"
              }
            />
            <Row label="Drug Class" value={med.drug_class} />
            {med.sub_class && <Row label="Sub-class" value={med.sub_class} />}
            <Row
              label="Half-life"
              value={
                med.half_life_hours !== null
                  ? `${med.half_life_hours} hours`
                  : "—"
              }
            />
            <Row
              label="Dose Range"
              value={med.common_dose_range ?? "—"}
            />
            {med.typical_start_dose_mg !== null && (
              <Row
                label="Typical Start Dose"
                value={`${med.typical_start_dose_mg} mg`}
              />
            )}
            {med.max_dose_mg !== null && (
              <Row label="Max Dose" value={`${med.max_dose_mg} mg`} />
            )}
            {med.dosing_frequency && (
              <Row label="Dosing Frequency" value={med.dosing_frequency} />
            )}
            {med.notes && <Row label="Notes" value={med.notes} />}

            {med.cyp450.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-500 mb-2">
                  CYP450 Profile
                </p>
                <ul className="space-y-1">
                  {med.cyp450.map((entry, i) => (
                    <li
                      key={i}
                      className="flex items-center gap-2 rounded bg-slate-50 px-3 py-1.5 text-xs"
                    >
                      <span className="font-medium text-slate-700">
                        {entry.enzyme}
                      </span>
                      <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-indigo-700">
                        {entry.relationship}
                      </span>
                      {entry.potency && (
                        <span className="text-slate-400">
                          ({entry.potency})
                        </span>
                      )}
                      {entry.fraction_metabolized !== null && (
                        <span className="text-slate-400">
                          fraction: {entry.fraction_metabolized}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="border-t border-slate-100 px-6 py-3 text-right">
        <button
          type="button"
          onClick={onClose}
          className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-700
                     hover:bg-slate-200 transition"
        >
          Close
        </button>
      </div>
    </dialog>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500 mb-0.5">{label}</p>
      <p>{value}</p>
    </div>
  );
}
