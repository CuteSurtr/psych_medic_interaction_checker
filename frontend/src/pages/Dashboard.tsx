import { useCallback, useEffect, useState } from "react";
import type {
  InteractionRow,
  MedicationSearchHit,
  PatientContext,
  RegimenItem,
  RiskSummary,
} from "../types";
import { apiUrl } from "../utils/api";
import AppHeader from "../components/AppHeader";
import MedicationSearch from "../components/MedicationSearch";
import RegimenList from "../components/RegimenList";
import PatientContextPanel from "../components/PatientContextPanel";
import { RegimenWarnings } from "../components/RegimenWarnings";
import InteractionGraph from "../components/InteractionGraph";
import InteractionDetailModal from "../components/InteractionDetailModal";
import MedicationDetailModal from "../components/MedicationDetailModal";
import RiskSummaryCards from "../components/RiskSummaryCards";
import InteractionTable from "../components/InteractionTable";
import DisclaimerFooter from "../components/DisclaimerFooter";

const QUICK_REGIMENS = [
  { label: "MDD Standard", ids: [6, 29] },
  { label: "Bipolar I", ids: [18, 15] },
  { label: "TRD Augmentation", ids: [7, 13, 20] },
  { label: "Schizophrenia", ids: [16] },
  { label: "ADHD + Anxiety", ids: [27, 5] },
];

const DEFAULT_PATIENT: PatientContext = {
  age: "",
  weight_kg: 70,
  smoking_status: false,
  egfr: "",
  hepatic_impairment: "none",
  pregnancy_status: false,
  cyp2d6_phenotype: "normal",
  cyp2c19_phenotype: "normal",
};

export default function Dashboard() {
  const [regimen, setRegimen] = useState<RegimenItem[]>([]);
  const [patient, setPatient] = useState<PatientContext>(DEFAULT_PATIENT);
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [interactionModal, setInteractionModal] =
    useState<InteractionRow | null>(null);
  const [medDetailId, setMedDetailId] = useState<number | null>(null);
  const [ctxOpen, setCtxOpen] = useState(false);

  const fetchSummary = useCallback(
    async (items: RegimenItem[], ctx: PatientContext) => {
      if (items.length < 2) {
        setSummary(null);
        return;
      }
      try {
        const res = await fetch(apiUrl("/api/risk-summary"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            medication_ids: items.map((m) => m.id),
            age: ctx.age === "" ? null : ctx.age,
            smoking_status: ctx.smoking_status,
            egfr: ctx.egfr === "" ? null : ctx.egfr,
            hepatic_impairment: ctx.hepatic_impairment,
            pregnancy_status: ctx.pregnancy_status,
            cyp2d6_phenotype: ctx.cyp2d6_phenotype,
            cyp2c19_phenotype: ctx.cyp2c19_phenotype,
          }),
        });
        if (!res.ok) throw new Error(res.statusText);
        const data: RiskSummary = await res.json();
        setSummary(data);
      } catch {
        setSummary(null);
      }
    },
    []
  );

  useEffect(() => {
    fetchSummary(regimen, patient);
  }, [regimen, patient, fetchSummary]);

  const addMed = (hit: MedicationSearchHit) => {
    setRegimen((prev) => {
      if (prev.some((m) => m.id === hit.id)) return prev;
      return [...prev, { ...hit }];
    });
  };

  const removeMed = (id: number) => {
    setRegimen((prev) => prev.filter((m) => m.id !== id));
  };

  const clearRegimen = () => {
    setRegimen([]);
    setSummary(null);
  };

  const changeDosage = (id: number, dosage: string) => {
    setRegimen((prev) =>
      prev.map((m) => (m.id === id ? { ...m, dosage } : m))
    );
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans">
      <AppHeader title="Drug Interaction Dashboard" />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Collapsible Patient Context */}
        <div>
          <button
            type="button"
            onClick={() => setCtxOpen((v) => !v)}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-5 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            <span>Patient Context</span>
            <svg
              className={`h-4 w-4 text-slate-400 transition-transform ${ctxOpen ? "rotate-180" : ""}`}
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
                clipRule="evenodd"
              />
            </svg>
          </button>
          {ctxOpen && (
            <div className="mt-2">
              <PatientContextPanel value={patient} onChange={setPatient} />
            </div>
          )}
        </div>

        {/* Regimen Warnings */}
        <RegimenWarnings regimen={regimen} patient={patient} />

        {/* Search is always visible */}
        <MedicationSearch onSelect={addMed} />

        {/* Quick Add */}
        {regimen.length === 0 && (
          <div className="flex flex-wrap gap-2">
            <span className="text-xs font-medium text-slate-500 self-center mr-1">Quick Add:</span>
            {QUICK_REGIMENS.map((qr) => (
              <button
                key={qr.label}
                type="button"
                onClick={() => qr.ids.forEach((id) => {
                  fetch(apiUrl(`/api/medications/${id}`))
                    .then(r => r.json())
                    .then((med: MedicationSearchHit) => addMed(med))
                    .catch(() => {});
                })}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 hover:bg-indigo-50 hover:border-indigo-300 hover:text-indigo-700 transition"
              >
                {qr.label}
              </button>
            ))}
          </div>
        )}

        {/* Empty state */}
        {regimen.length === 0 && summary === null && (
          <div className="rounded-lg border border-dashed border-slate-300 bg-white px-6 py-10 text-center">
            <p className="text-sm text-slate-500">
              Add medications above to begin checking for interactions.
            </p>
          </div>
        )}

        {/* No interactions detected */}
        {summary !== null && summary.interactions.length === 0 && regimen.length >= 2 && (
          <div className="rounded-lg border border-green-300 bg-green-50 px-5 py-3 text-sm font-medium text-green-800">
            {"\u2713"} No significant interactions detected in this regimen.
          </div>
        )}

        {/* Two-column grid */}
        {(regimen.length > 0 || summary !== null) && (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
            {/* Left column */}
            <div className="space-y-5 lg:col-span-3">
              <RegimenList
                items={regimen}
                onRemove={removeMed}
                onClear={clearRegimen}
                onDosageChange={changeDosage}
              />
              <InteractionTable
                interactions={summary?.interactions ?? []}
                onSelect={setInteractionModal}
              />
            </div>

            {/* Right column — graph */}
            <div className="rounded-lg border border-slate-200 bg-white p-3 lg:col-span-2">
              <InteractionGraph
                regimen={regimen}
                interactions={summary?.interactions ?? []}
                onSelectInteraction={setInteractionModal}
                onSelectMedication={setMedDetailId}
              />
            </div>
          </div>
        )}

        {/* Risk Summary */}
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            Risk Analysis
          </h2>
          <RiskSummaryCards summary={summary} />
        </section>

        {/* Modals */}
        <InteractionDetailModal
          open={interactionModal !== null}
          onClose={() => setInteractionModal(null)}
          row={interactionModal}
        />
        <MedicationDetailModal
          medId={medDetailId}
          onClose={() => setMedDetailId(null)}
        />
      </main>

      <DisclaimerFooter />
    </div>
  );
}
