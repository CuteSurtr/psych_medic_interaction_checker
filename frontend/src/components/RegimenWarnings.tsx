import { useMemo } from "react";
import type { PatientContext, RegimenItem } from "../types";

interface Warning {
  level: "critical" | "error" | "warning" | "info";
  message: string;
}

interface Props {
  regimen: RegimenItem[];
  patient: PatientContext;
}

export function RegimenWarnings({ regimen, patient }: Props) {
  const warnings = useMemo(() => {
    const w: Warning[] = [];
    const classCounts: Record<string, string[]> = {};

    for (const m of regimen) {
      const cls = m.drug_class.toUpperCase();
      if (!classCounts[cls]) classCounts[cls] = [];
      classCounts[cls].push(m.generic_name);
    }

    const hasMAOI = (classCounts["MAOI"] || []).length > 0;
    const hasSSRI = (classCounts["SSRI"] || []).length > 0;
    const hasSNRI = (classCounts["SNRI"] || []).length > 0;
    const hasTCA = (classCounts["TCA"] || []).length > 0;
    if (hasMAOI && (hasSSRI || hasSNRI || hasTCA)) {
      w.push({
        level: "critical",
        message:
          "FATAL COMBINATION: MAOI with serotonergic antidepressant. This combination is absolutely contraindicated due to life-threatening serotonin syndrome risk.",
      });
    }

    if ((classCounts["SSRI"] || []).length >= 2) {
      w.push({
        level: "error",
        message: `This regimen contains ${classCounts["SSRI"]!.length} SSRIs (${classCounts["SSRI"]!.join(", ")}). There is no clinical indication for concurrent SSRI therapy.`,
      });
    }

    const apCount =
      (classCounts["ATYPICAL ANTIPSYCHOTIC"] || []).length +
      (classCounts["TYPICAL ANTIPSYCHOTIC"] || []).length;
    if (apCount >= 2) {
      w.push({
        level: "warning",
        message: `This regimen contains ${apCount} antipsychotics. While sometimes clinically justified (e.g., cross-taper or clozapine augmentation), review for appropriateness.`,
      });
    }

    if ((classCounts["BENZODIAZEPINE"] || []).length >= 2) {
      w.push({
        level: "warning",
        message: `This regimen contains ${classCounts["BENZODIAZEPINE"]!.length} benzodiazepines. Consider consolidating to a single agent.`,
      });
    }

    const age = typeof patient.age === "number" ? patient.age : 0;
    if (age >= 65 && (classCounts["BENZODIAZEPINE"] || []).length >= 1) {
      w.push({
        level: "warning",
        message:
          "Benzodiazepine prescribed for patient \u226565. Beers Criteria recommends avoiding benzodiazepines in older adults due to fall and cognitive impairment risk.",
      });
    }

    if (regimen.length >= 5) {
      w.push({
        level: "info",
        message: `${regimen.length} concurrent psychiatric medications. Consider reviewing for polypharmacy reduction opportunities.`,
      });
    }

    return w;
  }, [regimen, patient]);

  if (warnings.length === 0) return null;

  const styles: Record<string, string> = {
    critical: "border-red-600 bg-red-50 text-red-900",
    error: "border-orange-500 bg-orange-50 text-orange-900",
    warning: "border-amber-500 bg-amber-50 text-amber-900",
    info: "border-blue-400 bg-blue-50 text-blue-900",
  };

  const icons: Record<string, string> = {
    critical: "\u26D4",
    error: "\u26A0\uFE0F",
    warning: "\u26A0\uFE0F",
    info: "\u2139\uFE0F",
  };

  return (
    <div className="space-y-2">
      {warnings.map((w, i) => (
        <div
          key={i}
          className={`rounded-lg border-l-4 p-3 text-sm font-medium ${styles[w.level] || styles.info}`}
          role="alert"
        >
          <span className="mr-2">{icons[w.level]}</span>
          {w.message}
        </div>
      ))}
    </div>
  );
}
