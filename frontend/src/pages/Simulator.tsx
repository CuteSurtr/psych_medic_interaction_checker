import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type {
  DoseEventInput,
  MedicationDetail,
  MedicationSearchHit,
  PatientContext,
  RegimenItem,
  SimulationResult,
  SimulationSpec,
} from "../types";
import { apiUrl } from "../utils/api";
import AppHeader from "../components/AppHeader";
import PatientContextPanel from "../components/PatientContextPanel";
import MedicationSearch from "../components/MedicationSearch";
import RegimenList from "../components/RegimenList";
import DoseTimelineEditor from "../components/DoseTimelineEditor";
import ConcentrationPlot from "../components/ConcentrationPlot";
import { WashoutCalculator } from "../components/WashoutCalculator";
import SteadyStateSummary from "../components/SteadyStateSummary";
import TissueDistributionPanel from "../components/TissueDistributionPanel";
import ReceptorOccupancyPanel from "../components/ReceptorOccupancyPanel";
import HepaticExtractionPanel from "../components/HepaticExtractionPanel";
import BayesianPKPanel from "../components/BayesianPKPanel";
import DosingScheduler from "../components/DosingScheduler";
import ManualTaperPlanner from "../components/ManualTaperPlanner";
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

interface MedMeta {
  generic_name: string;
  therapeutic_min_ng_ml?: number | null;
  therapeutic_max_ng_ml?: number | null;
  drug_class: string;
  cns_depression_risk?: number;
}

interface TaperResult {
  recommendations: string[];
  risk_timeline: { day: number; risk: number }[];
  total_cost: number;
}

export default function Simulator() {
  const [regimen, setRegimen] = useState<RegimenItem[]>([]);
  const [patient, setPatient] = useState<PatientContext>(DEFAULT_PATIENT);
  const [doseEvents, setDoseEvents] = useState<DoseEventInput[]>([]);
  const [simulationResult, setSimulationResult] =
    useState<SimulationResult | null>(null);
  const [simulationSpec, setSimulationSpec] = useState<SimulationSpec | null>(null);
  const [horizonDays, setHorizonDays] = useState(56);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [medMetas, setMedMetas] = useState<Map<number, MedMeta>>(new Map());

  const [comparisonMode, setComparisonMode] = useState(false);

  const [taperOpen, setTaperOpen] = useState(false);
  const [taperDrugIdx, setTaperDrugIdx] = useState(0);
  const [taperStartDose, setTaperStartDose] = useState(40);
  const [taperTargetDose, setTaperTargetDose] = useState(0);
  const [taperDuration, setTaperDuration] = useState(56);
  const [taperLoading, setTaperLoading] = useState(false);
  const [taperResult, setTaperResult] = useState<TaperResult | null>(null);
  const [taperError, setTaperError] = useState<string | null>(null);

  const [searchParams] = useSearchParams();

  // Load a scenario template when ?scenario=N is present in the URL
  useEffect(() => {
    const scenarioId = searchParams.get("scenario");
    if (!scenarioId) return;
    let cancelled = false;
    fetch(apiUrl(`/api/simulation/templates/${scenarioId}`))
      .then((r) => { if (!r.ok) throw new Error(r.statusText); return r.json(); })
      .then(async (template: { medications?: string[]; dose_events?: { medication: string; event_type: string; day: number; dose_mg: number; frequency: string }[] }) => {
        if (cancelled) return;
        const medNames: string[] = template.medications ?? [];
        const hitMap = new Map<string, MedicationSearchHit>();
        await Promise.all(medNames.map(async (name) => {
          try {
            const res = await fetch(apiUrl(`/api/medications/search?q=${encodeURIComponent(name)}`));
            if (!res.ok) return;
            const hits: MedicationSearchHit[] = await res.json();
            const exact = hits.find((h) => h.generic_name.toLowerCase() === name.toLowerCase()) ?? hits[0];
            if (exact) hitMap.set(name, exact);
          } catch { /* ignore */ }
        }));
        if (cancelled) return;
        const newRegimen: RegimenItem[] = [];
        for (const hit of hitMap.values()) {
          if (!newRegimen.some((m) => m.id === hit.id)) newRegimen.push({ ...hit });
        }
        setRegimen(newRegimen);
        if (template.dose_events) {
          const events: DoseEventInput[] = template.dose_events.flatMap((ev) => {
            const hit = hitMap.get(ev.medication);
            if (!hit) return [];
            return [{
              medication_id: hit.id,
              medication_name: hit.generic_name,
              event_type: ev.event_type as DoseEventInput["event_type"],
              event_day: ev.day,
              dose_mg: ev.dose_mg,
              frequency: ev.frequency,
            }];
          });
          setDoseEvents(events);
        }
        for (const hit of hitMap.values()) fetchMedDetail(hit.id);
      })
      .catch(() => { /* ignore — just leave the simulator empty */ });
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchMedDetail = useCallback(async (id: number) => {
    try {
      const res = await fetch(apiUrl(`/api/medications/${id}`));
      if (!res.ok) return;
      const detail: MedicationDetail = await res.json();
      setMedMetas((prev) => {
        const next = new Map(prev);
        next.set(id, {
          generic_name: detail.generic_name,
          therapeutic_min_ng_ml: detail.therapeutic_min_ng_ml,
          therapeutic_max_ng_ml: detail.therapeutic_max_ng_ml,
          drug_class: detail.drug_class,
          cns_depression_risk: detail.cns_depression_risk,
        });
        return next;
      });
    } catch {
      /* best-effort */
    }
  }, []);

  const addMed = (hit: MedicationSearchHit) => {
    setRegimen((prev) => {
      if (prev.some((m) => m.id === hit.id)) return prev;
      return [...prev, { ...hit }];
    });
    fetchMedDetail(hit.id);
  };

  const removeMed = (id: number) => {
    setRegimen((prev) => prev.filter((m) => m.id !== id));
    setDoseEvents((prev) => prev.filter((e) => e.medication_id !== id));
    setMedMetas((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  };

  const clearRegimen = () => {
    setRegimen([]);
    setDoseEvents([]);
    setSimulationResult(null);
    setSimulationSpec(null);
    setMedMetas(new Map());
  };

  const changeDosage = (id: number, dosage: string) => {
    setRegimen((prev) =>
      prev.map((m) => (m.id === id ? { ...m, dosage } : m))
    );
  };

  const runSimulation = async () => {
    if (doseEvents.length === 0) return;
    setLoading(true);
    setError(null);
    setSimulationResult(null);

    const schedules = doseEvents.map((e) => ({
      medication_id: e.medication_id,
      event_type: e.event_type,
      event_day: e.event_day,
      dose_mg: e.dose_mg,
      frequency: e.frequency,
    }));
    const spec: SimulationSpec = {
      patient_weight_kg: patient.weight_kg === "" ? 70 : patient.weight_kg,
      smoking_status: patient.smoking_status,
      cyp2d6_phenotype: patient.cyp2d6_phenotype,
      cyp2c19_phenotype: patient.cyp2c19_phenotype,
      horizon_days: horizonDays,
      dose_schedules: schedules,
    };

    try {
      // One request configures and runs the simulation. The downstream
      // analysis panels receive the same spec inline, so no server-side state
      // has to survive between calls.
      const runRes = await fetch(apiUrl("/api/simulation/run"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          patient_age: patient.age === "" ? null : patient.age,
          egfr: patient.egfr === "" ? null : patient.egfr,
          hepatic_impairment: patient.hepatic_impairment,
          pregnancy_status: patient.pregnancy_status,
          ...spec,
        }),
      });
      if (!runRes.ok) throw new Error(`Run failed: ${runRes.statusText}`);
      const result: SimulationResult = await runRes.json();
      setSimulationResult(result);
      setSimulationSpec(spec);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "";
      setError(
        msg ||
          "Simulation could not converge. This may occur with certain drug combinations. Please verify parameters."
      );
    } finally {
      setLoading(false);
    }
  };

  const runTaper = async () => {
    if (regimen.length === 0) return;
    setTaperLoading(true);
    setTaperError(null);
    setTaperResult(null);

    const drugName =
      medMetas.get(regimen[taperDrugIdx]?.id)?.generic_name ??
      regimen[taperDrugIdx]?.generic_name ??
      "unknown";

    try {
      const res = await fetch(apiUrl("/api/advanced/optimizer/taper"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          drug_name: drugName,
          start_dose: taperStartDose,
          target_dose: taperTargetDose,
          duration_days: taperDuration,
        }),
      });
      if (!res.ok) throw new Error(`Taper request failed: ${res.statusText}`);
      const data: TaperResult = await res.json();
      setTaperResult(data);
    } catch (err) {
      setTaperError(
        err instanceof Error ? err.message : "Taper optimization failed"
      );
    } finally {
      setTaperLoading(false);
    }
  };

  const medications: MedMeta[] = regimen.map((r) => {
    const meta = medMetas.get(r.id);
    return {
      generic_name: r.generic_name,
      therapeutic_min_ng_ml: meta?.therapeutic_min_ng_ml ?? null,
      therapeutic_max_ng_ml: meta?.therapeutic_max_ng_ml ?? null,
      drug_class: r.drug_class,
    };
  });

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans">
      <AppHeader title="PK Simulator" />

      <main className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 sm:px-6 lg:px-8">
        {/* Comparison Mode toggle */}
        <div className="flex items-center gap-3">
          <label className="relative inline-flex cursor-pointer items-center">
            <input
              type="checkbox"
              checked={comparisonMode}
              onChange={(e) => setComparisonMode(e.target.checked)}
              className="peer sr-only"
            />
            <div className="h-5 w-9 rounded-full bg-slate-300 after:absolute after:left-[2px] after:top-[2px]
                            after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-all
                            peer-checked:bg-indigo-600 peer-checked:after:translate-x-full" />
          </label>
          <span className="text-sm font-medium text-slate-700">Comparison Mode</span>
        </div>
        {comparisonMode && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            Comparison mode: Run simulation twice with different parameters to compare side-by-side. (Feature in development)
          </div>
        )}

        <PatientContextPanel value={patient} onChange={setPatient} />

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <MedicationSearch onSelect={addMed} />
          <div />
        </div>

        <RegimenList
          items={regimen}
          onRemove={removeMed}
          onClear={clearRegimen}
          onDosageChange={changeDosage}
        />

        <DoseTimelineEditor
          events={doseEvents}
          onChange={setDoseEvents}
          medications={regimen}
        />

        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={runSimulation}
            disabled={loading || doseEvents.length === 0}
            className="rounded-lg bg-indigo-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm
                       hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
          >
            {loading ? "Running\u2026" : "Run Simulation"}
          </button>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            Horizon
            <select
              value={horizonDays}
              onChange={(e) => setHorizonDays(Number(e.target.value))}
              className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            >
              <option value={14}>2 weeks</option>
              <option value={28}>4 weeks</option>
              <option value={42}>6 weeks</option>
              <option value={56}>8 weeks</option>
              <option value={84}>12 weeks</option>
              <option value={112}>16 weeks</option>
            </select>
          </label>
          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}
        </div>

        {loading && (
          <div className="flex items-center gap-3 rounded-lg border border-indigo-200 bg-indigo-50 px-5 py-4">
            <svg
              className="h-5 w-5 animate-spin text-indigo-600"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <span className="text-sm font-medium text-indigo-700">
              Computing pharmacokinetic model...
            </span>
          </div>
        )}

        {error && !loading && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
            Simulation could not converge. This may occur with certain drug
            combinations. Please verify parameters.
          </div>
        )}

        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            Concentration Curves
          </h2>
          <ConcentrationPlot result={simulationResult} medications={medications} />
        </section>

        {/* Monte Carlo Population Analysis */}
        <section className="rounded-lg border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-700">
            Monte Carlo Population Analysis
          </h2>
          <hr className="my-2 border-slate-200" />
          <p className="text-sm text-slate-600">
            Population variability simulation available via API.
            Run 10,000 virtual patients to see confidence intervals.
          </p>
          <span className="mt-2 inline-block rounded-md bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-500">
            Coming Soon &mdash; API endpoint available at{" "}
            <code className="text-indigo-600">/api/simulation/&#123;id&#125;/monte-carlo</code>
          </span>
        </section>

        <WashoutCalculator regimen={regimen} />

        {/* Dose Taper Optimizer */}
        <section className="rounded-lg border border-slate-200 bg-white">
          <button
            type="button"
            onClick={() => setTaperOpen((o) => !o)}
            className="flex w-full items-center justify-between px-5 py-4 text-left text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
          >
            Dose Taper Optimizer
            <svg
              className={`h-4 w-4 text-slate-400 transition-transform ${taperOpen ? "rotate-180" : ""}`}
              fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {taperOpen && (
            <div className="border-t border-slate-200 px-5 pb-5 pt-4 space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <label className="block text-sm text-slate-600">
                  Drug to taper
                  <select
                    value={taperDrugIdx}
                    onChange={(e) => setTaperDrugIdx(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  >
                    {regimen.length === 0 && <option>No drugs in regimen</option>}
                    {regimen.map((r, i) => (
                      <option key={r.id} value={i}>{r.generic_name}</option>
                    ))}
                  </select>
                </label>
                <label className="block text-sm text-slate-600">
                  Start Dose (mg)
                  <input
                    type="number"
                    min={0}
                    value={taperStartDose}
                    onChange={(e) => setTaperStartDose(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Target Dose (mg)
                  <input
                    type="number"
                    min={0}
                    value={taperTargetDose}
                    onChange={(e) => setTaperTargetDose(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                </label>
                <label className="block text-sm text-slate-600">
                  Duration (days)
                  <input
                    type="number"
                    min={1}
                    value={taperDuration}
                    onChange={(e) => setTaperDuration(Number(e.target.value))}
                    className="mt-1 block w-full rounded-md border border-slate-300 px-2 py-1.5 text-sm"
                  />
                </label>
              </div>

              <button
                type="button"
                onClick={runTaper}
                disabled={taperLoading || regimen.length === 0}
                className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white shadow-sm
                           hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
              >
                {taperLoading ? "Computing\u2026" : "Compute Optimal Taper"}
              </button>

              {taperError && (
                <p className="text-sm text-red-600">{taperError}</p>
              )}

              {taperResult && (
                <div className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-slate-700">Recommendations</h3>
                    <ol className="mt-1 list-inside list-decimal space-y-1 text-sm text-slate-600">
                      {taperResult.recommendations.map((rec, i) => (
                        <li key={i}>{rec}</li>
                      ))}
                    </ol>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-slate-700">Risk Timeline</h3>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {taperResult.risk_timeline.map((point, i) => (
                        <span
                          key={i}
                          title={`Day ${point.day}: risk ${point.risk.toFixed(2)}`}
                          className={`inline-block h-3 w-3 rounded-full ${
                            point.risk < 0.3
                              ? "bg-green-500"
                              : point.risk < 0.7
                                ? "bg-yellow-400"
                                : "bg-red-500"
                          }`}
                        />
                      ))}
                    </div>
                    <p className="mt-1 text-xs text-slate-400">
                      <span className="inline-block h-2 w-2 rounded-full bg-green-500" /> low
                      {" "}<span className="inline-block h-2 w-2 rounded-full bg-yellow-400" /> moderate
                      {" "}<span className="inline-block h-2 w-2 rounded-full bg-red-500" /> high
                    </p>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-slate-700">Total Cost Score</h3>
                    <p className="text-lg font-bold text-slate-800">{taperResult.total_cost.toFixed(2)}</p>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">
            Steady-State Summary
          </h2>
          <SteadyStateSummary
            info={simulationResult?.steady_state_info ?? null}
          />
        </section>

        <DosingScheduler
          medications={regimen.map((r) => ({
            generic_name: r.generic_name,
            drug_class: r.drug_class,
            cns_depression_risk: medMetas.get(r.id)?.cns_depression_risk,
          }))}
        />

        <TissueDistributionPanel simulation={simulationSpec} />
        <ReceptorOccupancyPanel simulation={simulationSpec} />
        <HepaticExtractionPanel
          medicationIds={regimen.map((r) => r.id)}
          simulation={simulationSpec}
        />
        <ManualTaperPlanner />
        <BayesianPKPanel />
      </main>

      <DisclaimerFooter />
    </div>
  );
}
