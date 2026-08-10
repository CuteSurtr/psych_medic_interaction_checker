import { useCallback, useEffect, useRef, useState } from "react";
import type {
  InteractionRow,
  MedicationSearchHit,
  PatientContext,
  RegimenItem,
  RiskSummary,
} from "../types";
import { apiUrl } from "../utils/api";
import { SEVERITY_COLORS } from "../utils/colorSchemes";
import AppHeader from "../components/AppHeader";
import PatientContextPanel from "../components/PatientContextPanel";
import MedicationSearch from "../components/MedicationSearch";
import RegimenList from "../components/RegimenList";
import DisclaimerFooter from "../components/DisclaimerFooter";

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

export default function Report() {
  const [regimen, setRegimen] = useState<RegimenItem[]>([]);
  const [patient, setPatient] = useState<PatientContext>(DEFAULT_PATIENT);
  const [summary, setSummary] = useState<RiskSummary | null>(null);
  const [builderOpen, setBuilderOpen] = useState(true);

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

  const [copied, setCopied] = useState(false);
  const copiedTimer = useRef<ReturnType<typeof setTimeout>>();

  const copyToClipboard = useCallback(() => {
    const ts = new Date().toLocaleString();
    const lines: string[] = [
      "NeuroTrace \u2014 Psychiatric Medication Interaction Report",
      `Generated: ${ts}`,
      "DISCLAIMER: This report is for educational purposes only. It does not constitute medical advice.",
      "",
      "PATIENT CONTEXT",
      `Age: ${patient.age === "" ? "Not specified" : patient.age} | Smoking: ${patient.smoking_status ? "Yes" : "No"} | CYP2D6: ${patient.cyp2d6_phenotype} | CYP2C19: ${patient.cyp2c19_phenotype}`,
      "",
      "CURRENT MEDICATION REGIMEN",
    ];
    regimen.forEach((m, i) => {
      lines.push(`${i + 1}. ${m.generic_name} (${m.drug_class})${m.dosage ? ` — ${m.dosage}` : ""}`);
    });
    if (summary) {
      lines.push("");
      lines.push("INTERACTION SUMMARY");
      const counts = summary.counts_by_severity;
      const parts = Object.entries(counts)
        .map(([k, v]) => `${v} ${k}`)
        .join(", ");
      lines.push(`Total: ${summary.interactions.length} interactions (${parts})`);
      for (const row of summary.interactions) {
        lines.push("");
        lines.push(`[${row.severity}] ${row.drug_a_name} & ${row.drug_b_name}`);
        lines.push(`  Mechanism: ${row.mechanism_type} — ${row.mechanism_detail}`);
        lines.push(`  Effect: ${row.clinical_effect}`);
        lines.push(`  Recommendation: ${row.recommendation}`);
      }
      lines.push("");
      lines.push("RISK ASSESSMENT");
      lines.push(
        `Serotonin: ${summary.serotonin_risk} | QTc: ${summary.qtc_risk} | ACB: ${summary.anticholinergic_burden} | CNS: ${summary.cns_depression_risk}`
      );
    }
    navigator.clipboard.writeText(lines.join("\n")).then(() => {
      setCopied(true);
      clearTimeout(copiedTimer.current);
      copiedTimer.current = setTimeout(() => setCopied(false), 2000);
    });
  }, [regimen, patient, summary]);

  const timestamp = new Date().toLocaleString();

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans">
      <AppHeader title="Clinical Report" />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Collapsible regimen builder */}
        <div className="print:hidden">
          <button
            type="button"
            onClick={() => setBuilderOpen((v) => !v)}
            className="flex w-full items-center justify-between rounded-lg border border-slate-200 bg-white px-5 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50"
          >
            <span>Build Regimen</span>
            <svg
              className={`h-4 w-4 text-slate-400 transition-transform ${builderOpen ? "rotate-180" : ""}`}
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
          {builderOpen && (
            <div className="mt-3 space-y-4">
              <PatientContextPanel value={patient} onChange={setPatient} />
              <MedicationSearch onSelect={addMed} />
              <RegimenList
                items={regimen}
                onRemove={removeMed}
                onClear={clearRegimen}
                onDosageChange={changeDosage}
              />
            </div>
          )}
        </div>

        {/* Print & Copy buttons */}
        <div className="flex gap-3 print:hidden">
          <button
            type="button"
            onClick={() => window.print()}
            disabled={regimen.length === 0}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            Print / Save PDF
          </button>
          <button
            type="button"
            onClick={copyToClipboard}
            disabled={regimen.length === 0}
            className="rounded-lg border border-slate-300 bg-white px-5 py-2.5 text-sm font-semibold text-slate-700 shadow-sm
                       hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {copied ? "Copied!" : "Copy to Clipboard"}
          </button>
        </div>

        {/* Report Content */}
        <div className="rounded-lg border border-slate-200 bg-white p-6 print:border-none print:p-0 print:shadow-none">
          <div className="mb-6 border-b border-slate-100 pb-4">
            <h2 className="text-lg font-bold text-slate-800">
              NeuroTrace Clinical Report
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Generated: {timestamp}
            </p>
          </div>

          {/* Patient Context */}
          <section className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">
              Patient Context
            </h3>
            <ul className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm text-slate-600 sm:grid-cols-4">
              <li>
                <span className="font-medium text-slate-500">Age:</span>{" "}
                {patient.age === "" ? "Not specified" : patient.age}
              </li>
              <li>
                <span className="font-medium text-slate-500">Weight:</span>{" "}
                {patient.weight_kg} kg
              </li>
              <li>
                <span className="font-medium text-slate-500">Smoking:</span>{" "}
                {patient.smoking_status ? "Yes" : "No"}
              </li>
              <li>
                <span className="font-medium text-slate-500">eGFR:</span>{" "}
                {patient.egfr === "" ? "Not specified" : `${patient.egfr} mL/min`}
              </li>
              <li>
                <span className="font-medium text-slate-500">Hepatic:</span>{" "}
                {patient.hepatic_impairment}
              </li>
              <li>
                <span className="font-medium text-slate-500">Pregnancy:</span>{" "}
                {patient.pregnancy_status ? "Yes" : "No"}
              </li>
              <li>
                <span className="font-medium text-slate-500">CYP2D6:</span>{" "}
                {patient.cyp2d6_phenotype}
              </li>
              <li>
                <span className="font-medium text-slate-500">CYP2C19:</span>{" "}
                {patient.cyp2c19_phenotype}
              </li>
            </ul>
          </section>

          {/* Medication list */}
          <section className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">
              Medications ({regimen.length})
            </h3>
            {regimen.length === 0 ? (
              <p className="text-sm text-slate-400">No medications added.</p>
            ) : (
              <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
                {regimen.map((m) => (
                  <li key={m.id} className="flex items-center justify-between px-4 py-2.5">
                    <div>
                      <span className="font-medium text-slate-700">
                        {m.generic_name}
                      </span>
                      <span className="ml-2 text-xs text-slate-400">
                        {m.drug_class}
                      </span>
                    </div>
                    {m.dosage && (
                      <span className="text-xs text-slate-500">{m.dosage}</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Risk Summary */}
          {summary && (
            <section className="mb-6">
              <h3 className="mb-2 text-sm font-semibold text-slate-700">
                Risk Summary
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                <RiskPill label="Serotonin" value={summary.serotonin_risk} />
                <RiskPill label="QTc" value={summary.qtc_risk} />
                <RiskPill
                  label="Anticholinergic"
                  value={String(summary.anticholinergic_burden)}
                />
                <RiskPill label="CNS Depression" value={summary.cns_depression_risk} />
              </div>
              {summary.contextual_notes.length > 0 && (
                <ul className="mt-3 space-y-1 text-xs text-slate-600">
                  {summary.contextual_notes.map((note, i) => (
                    <li key={i} className="flex items-start gap-1.5">
                      <span className="mt-0.5 block h-1.5 w-1.5 flex-shrink-0 rounded-full bg-slate-400" />
                      {note}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}

          {/* All interactions */}
          {summary && summary.interactions.length > 0 && (
            <section>
              <h3 className="mb-2 text-sm font-semibold text-slate-700">
                All Interactions ({summary.interactions.length})
              </h3>
              <div className="space-y-3">
                {summary.interactions.map((row, idx) => (
                  <InteractionBlock key={idx} row={row} />
                ))}
              </div>
            </section>
          )}
        </div>
      </main>

      <DisclaimerFooter />
    </div>
  );
}

function RiskPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-center">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-bold text-slate-700">{value}</p>
    </div>
  );
}

function InteractionBlock({ row }: { row: InteractionRow }) {
  const sevKey = row.severity.toLowerCase();
  const sevColor = SEVERITY_COLORS[sevKey] ?? SEVERITY_COLORS.minor;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 text-sm">
      <div className="mb-2 flex items-center gap-2">
        <span className="font-semibold text-slate-800">
          {row.drug_a_name} &amp; {row.drug_b_name}
        </span>
        <span
          className="inline-block rounded-full px-2 py-0.5 text-xs font-semibold text-white"
          style={{ backgroundColor: sevColor }}
        >
          {row.severity}
        </span>
      </div>
      <dl className="grid grid-cols-1 gap-y-1 text-xs text-slate-600 sm:grid-cols-2">
        <div>
          <dt className="font-semibold text-slate-500">Mechanism</dt>
          <dd>{row.mechanism_type} — {row.mechanism_detail}</dd>
        </div>
        <div>
          <dt className="font-semibold text-slate-500">Clinical Effect</dt>
          <dd>{row.clinical_effect}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="font-semibold text-slate-500">Recommendation</dt>
          <dd>{row.recommendation}</dd>
        </div>
        {row.evidence_level && (
          <div>
            <dt className="font-semibold text-slate-500">Evidence</dt>
            <dd>{row.evidence_level}</dd>
          </div>
        )}
      </dl>
    </div>
  );
}
