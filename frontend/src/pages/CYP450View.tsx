import { useEffect, useState } from "react";
import type {
  MedicationSearchHit,
  MedicationDetail,
  PatientContext,
  RegimenItem,
} from "../types";
import { apiUrl } from "../utils/api";
import AppHeader from "../components/AppHeader";
import PatientContextPanel from "../components/PatientContextPanel";
import MedicationSearch from "../components/MedicationSearch";
import RegimenList from "../components/RegimenList";
import CYP450Diagram from "../components/CYP450Diagram";
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

interface EntropyResult {
  cdi: number;
  dominant_enzyme: string;
  /** 0–100 from API (`dominant_enzyme_pct`). */
  dominant_enzyme_pct: number;
  interpretation: string;
}

export default function CYP450View() {
  const [regimen, setRegimen] = useState<RegimenItem[]>([]);
  const [patient, setPatient] = useState<PatientContext>(DEFAULT_PATIENT);
  const [medDetails, setMedDetails] = useState<Map<number, MedicationDetail>>(
    new Map()
  );
  const [entropy, setEntropy] = useState<EntropyResult | null>(null);
  const [entropyLoading, setEntropyLoading] = useState(false);

  useEffect(() => {
    if (regimen.length === 0) {
      setMedDetails(new Map());
      setEntropy(null);
      return;
    }
    let cancelled = false;
    const fetchAll = async () => {
      const next = new Map<number, MedicationDetail>();
      await Promise.all(
        regimen.map(async (r) => {
          try {
            const res = await fetch(apiUrl(`/api/medications/${r.id}`));
            if (res.ok) {
              const data: MedicationDetail = await res.json();
              next.set(r.id, data);
            }
          } catch {
            /* network errors silently ignored */
          }
        })
      );
      if (!cancelled) setMedDetails(next);
    };
    fetchAll();
    return () => {
      cancelled = true;
    };
  }, [regimen]);

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
  };

  const changeDosage = (id: number, dosage: string) => {
    setRegimen((prev) =>
      prev.map((m) => (m.id === id ? { ...m, dosage } : m))
    );
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans">
      <AppHeader title="CYP450 Pathways" />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        <PatientContextPanel value={patient} onChange={setPatient} />

        <MedicationSearch onSelect={addMed} />

        <RegimenList
          items={regimen}
          onRemove={removeMed}
          onClear={clearRegimen}
          onDosageChange={changeDosage}
        />

        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            Enzyme Pathway Map
          </h2>
          <CYP450Diagram
            regimen={regimen}
            cyp2d6={patient.cyp2d6_phenotype}
            cyp2c19={patient.cyp2c19_phenotype}
          />
        </section>

        {/* ── Phenotype Impact Summary ── */}
        {regimen.length > 0 &&
          (patient.cyp2d6_phenotype !== "normal" ||
            patient.cyp2c19_phenotype !== "normal") && (
            <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
              <h2 className="mb-4 text-sm font-semibold text-amber-800">
                Phenotype Impact Summary
              </h2>

              <div className="space-y-4">
                {regimen.map((med) => {
                  const detail = medDetails.get(med.id);
                  if (!detail) return null;

                  const impacts: {
                    enzyme: string;
                    phenotype: string;
                    fraction: number;
                  }[] = [];

                  detail.cyp450.forEach((entry) => {
                    if (entry.relationship !== "substrate") return;
                    const frac = entry.fraction_metabolized ?? 0;

                    if (
                      entry.enzyme.toUpperCase() === "CYP2D6" &&
                      patient.cyp2d6_phenotype !== "normal"
                    ) {
                      impacts.push({
                        enzyme: "CYP2D6",
                        phenotype: patient.cyp2d6_phenotype,
                        fraction: frac,
                      });
                    }
                    if (
                      entry.enzyme.toUpperCase() === "CYP2C19" &&
                      patient.cyp2c19_phenotype !== "normal"
                    ) {
                      impacts.push({
                        enzyme: "CYP2C19",
                        phenotype: patient.cyp2c19_phenotype,
                        fraction: frac,
                      });
                    }
                  });

                  if (impacts.length === 0) return null;

                  return (
                    <div
                      key={med.id}
                      className="rounded-lg border border-amber-300 bg-white p-4"
                    >
                      {impacts.map((imp) => {
                        const pctIncrease = Math.round(imp.fraction * 100);
                        let recommendation: string;
                        if (imp.fraction >= 0.3) {
                          recommendation =
                            "Consider dose reduction or alternative agent.";
                        } else if (imp.fraction < 0.1) {
                          recommendation =
                            "Minimal clinical impact expected.";
                        } else {
                          recommendation =
                            "Monitor for increased side effects.";
                        }

                        return (
                          <div key={imp.enzyme} className="mb-2 last:mb-0">
                            <p className="text-xs font-semibold text-amber-700">
                              {imp.enzyme}{" "}
                              <span className="capitalize">
                                {imp.phenotype}
                              </span>{" "}
                              Metabolizer Impact:
                            </p>
                            <p className="mt-1 text-sm text-slate-800">
                              •{" "}
                              <span className="font-medium">
                                {detail.generic_name}
                              </span>
                              : Expected ~{pctIncrease}% increase in plasma
                              levels.
                            </p>
                            <p className="ml-3 text-xs text-slate-600">
                              {recommendation}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  );
                })}
              </div>
            </section>
          )}

        {/* ── Metabolic Entropy (CDI) ── */}
        {regimen.length > 0 && (
          <section className="rounded-xl border border-slate-200 bg-white p-5">
            <h2 className="mb-4 text-sm font-semibold text-slate-700">
              Metabolic Entropy
            </h2>

            <button
              disabled={entropyLoading}
              onClick={async () => {
                setEntropyLoading(true);
                setEntropy(null);
                try {
                  const ids = regimen.map((r) => r.id).join(",");
                  const res = await fetch(
                    apiUrl(
                      `/api/advanced/entropy?medication_ids=${ids}`
                    )
                  );
                  if (res.ok) {
                    const data: EntropyResult = await res.json();
                    setEntropy(data);
                  }
                } catch {
                  /* network errors silently ignored */
                } finally {
                  setEntropyLoading(false);
                }
              }}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:opacity-50"
            >
              {entropyLoading ? "Computing…" : "Compute CDI"}
            </button>

            {entropy && (
              <div className="mt-4 space-y-3">
                {/* CDI progress bar */}
                <div>
                  <div className="mb-1 flex items-center justify-between text-xs text-slate-600">
                    <span>CDI Score</span>
                    <span className="font-mono font-semibold">
                      {entropy.cdi.toFixed(3)}
                    </span>
                  </div>
                  <div className="h-3 w-full overflow-hidden rounded-full bg-slate-200">
                    <div
                      className={`h-full rounded-full transition-all ${
                        entropy.cdi >= 0.8
                          ? "bg-green-500"
                          : entropy.cdi >= 0.5
                            ? "bg-yellow-500"
                            : "bg-red-500"
                      }`}
                      style={{ width: `${Math.min(entropy.cdi * 100, 100)}%` }}
                    />
                  </div>
                </div>

                {/* Dominant enzyme */}
                <p className="text-sm text-slate-700">
                  <span className="font-medium">Dominant pathway:</span>{" "}
                  {entropy.dominant_enzyme} ({entropy.dominant_enzyme_pct.toFixed(1)}%)
                </p>

                {/* Interpretation */}
                <p className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm text-slate-600">
                  {entropy.interpretation}
                </p>
              </div>
            )}
          </section>
        )}
      </main>

      <DisclaimerFooter />
    </div>
  );
}
