import { useEffect, useRef } from "react";
import type { InteractionRow } from "../types";
import { SEVERITY_COLORS } from "../utils/colorSchemes";

interface Props {
  open: boolean;
  onClose: () => void;
  row: InteractionRow | null;
}

export default function InteractionDetailModal({ open, onClose, row }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    else if (!open && el.open) el.close();
  }, [open]);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    const handler = () => onClose();
    el.addEventListener("close", handler);
    return () => el.removeEventListener("close", handler);
  }, [onClose]);

  if (!row) return null;

  const sevKey = row.severity.toLowerCase();
  const sevColor = SEVERITY_COLORS[sevKey] ?? SEVERITY_COLORS.minor;

  return (
    <dialog
      ref={dialogRef}
      aria-modal="true"
      aria-label="Interaction details"
      className="m-auto w-full max-w-lg rounded-xl border border-slate-200 bg-white p-0 shadow-2xl backdrop:bg-black/40"
    >
      <div className="flex items-start justify-between border-b border-slate-100 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">
            {row.drug_a_name} &amp; {row.drug_b_name}
          </h2>
          <span
            className="mt-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold text-white"
            style={{ backgroundColor: sevColor }}
          >
            {row.severity}
          </span>
        </div>
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

      <div className="space-y-4 px-6 py-5 text-sm text-slate-700">
        <Section label="Mechanism Type" value={row.mechanism_type} />
        <Section label="Mechanism Detail" value={row.mechanism_detail} />
        <Section label="Clinical Effect" value={row.clinical_effect} />
        <Section label="Recommendation" value={row.recommendation} />
        {row.evidence_level && (
          <Section label="Evidence Level" value={row.evidence_level} />
        )}
        {row.references && row.references.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 mb-1">
              References
            </p>
            <ul className="list-disc list-inside space-y-0.5 text-xs text-slate-600">
              {row.references.map((ref, i) => (
                <li key={i}>{ref}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 px-6 py-3">
        <div className="flex gap-2">
          {row.mechanism_type &&
            /pk|pharmacokinetic/i.test(row.mechanism_type) && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    window.location.href = "/simulator";
                  }}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  Simulate This Interaction
                </button>
                <button
                  type="button"
                  onClick={() => {
                    window.location.href = "/cyp450";
                  }}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 transition"
                >
                  View CYP450 Pathway
                </button>
              </>
            )}
        </div>
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

function Section({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold text-slate-500 mb-0.5">{label}</p>
      <p>{value}</p>
    </div>
  );
}
