import { useEffect, useState } from "react";
import type { CYP450Entry, RegimenItem } from "../types";
import { apiUrl } from "../utils/api";

interface Props {
  regimen: RegimenItem[];
  cyp2d6: string;
  cyp2c19: string;
}

interface EnzymeProfile {
  enzyme: string;
  substrates: { drug: string; fraction: number | null }[];
  inhibitors: { drug: string; potency: string | null }[];
  inducers: { drug: string; potency: string | null }[];
}

const ENZYME_ORDER = ["CYP2D6", "CYP3A4", "CYP1A2", "CYP2C19", "CYP2C9", "UGT1A4"];

export default function CYP450Diagram({ regimen, cyp2d6, cyp2c19 }: Props) {
  const [profiles, setProfiles] = useState<EnzymeProfile[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (regimen.length === 0) {
      setProfiles([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    const ids = regimen.map((m) => m.id).join(",");
    fetch(apiUrl(`/api/cyp450/profile?medication_ids=${ids}&cyp2d6_phenotype=${cyp2d6}&cyp2c19_phenotype=${cyp2c19}`))
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: { medication_id: number; generic_name: string; entries: CYP450Entry[] }[]) => {
        if (cancelled) return;

        const enzymeMap = new Map<string, EnzymeProfile>();
        for (const enz of ENZYME_ORDER) {
          enzymeMap.set(enz, {
            enzyme: enz,
            substrates: [],
            inhibitors: [],
            inducers: [],
          });
        }

        for (const med of data) {
          for (const entry of med.entries) {
            let profile = enzymeMap.get(entry.enzyme);
            if (!profile) {
              profile = {
                enzyme: entry.enzyme,
                substrates: [],
                inhibitors: [],
                inducers: [],
              };
              enzymeMap.set(entry.enzyme, profile);
            }
            const rel = entry.relationship.toLowerCase();
            if (rel === "substrate") {
              profile.substrates.push({
                drug: med.generic_name,
                fraction: entry.fraction_metabolized,
              });
            } else if (rel === "inhibitor") {
              profile.inhibitors.push({
                drug: med.generic_name,
                potency: entry.potency,
              });
            } else if (rel === "inducer") {
              profile.inducers.push({
                drug: med.generic_name,
                potency: entry.potency,
              });
            }
          }
        }

        const result: EnzymeProfile[] = [];
        for (const enz of ENZYME_ORDER) {
          const p = enzymeMap.get(enz);
          if (p) result.push(p);
        }
        for (const [key, p] of enzymeMap.entries()) {
          if (!ENZYME_ORDER.includes(key)) result.push(p);
        }
        setProfiles(result);
      })
      .catch(() => {
        if (!cancelled) setProfiles([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [regimen, cyp2d6, cyp2c19]);

  const hasConflict = (p: EnzymeProfile): boolean =>
    p.substrates.length > 0 && (p.inhibitors.length > 0 || p.inducers.length > 0);

  if (regimen.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
        Add medications to view CYP450 pathway interactions.
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex h-40 items-center justify-center text-sm text-slate-400">
        Loading CYP450 profiles…
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-xs text-slate-500">
        <span className="rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">
          CYP2D6: {cyp2d6}
        </span>
        <span className="rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">
          CYP2C19: {cyp2c19}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {profiles.map((p) => {
          const conflict = hasConflict(p);
          return (
            <div
              key={p.enzyme}
              className={`rounded-lg border bg-white p-4 ${
                conflict
                  ? "border-red-400 ring-1 ring-red-200"
                  : "border-slate-200"
              }`}
            >
              <h4 className="mb-2 text-sm font-semibold text-slate-700">
                {p.enzyme}
                {conflict && (
                  <span className="ml-2 text-xs font-normal text-red-500">
                    conflict
                  </span>
                )}
              </h4>

              <Bucket label="Substrates" color="blue">
                {p.substrates.map((s, i) => (
                  <span key={i}>
                    {s.drug}
                    {s.fraction !== null && (
                      <span className="text-slate-400">
                        {" "}
                        ({(s.fraction * 100).toFixed(0)}%)
                      </span>
                    )}
                  </span>
                ))}
              </Bucket>

              <Bucket label="Inhibitors" color="red">
                {p.inhibitors.map((s, i) => (
                  <span key={i}>
                    {s.drug}
                    {s.potency && (
                      <span className="text-slate-400"> ({s.potency})</span>
                    )}
                  </span>
                ))}
              </Bucket>

              <Bucket label="Inducers" color="amber">
                {p.inducers.map((s, i) => (
                  <span key={i}>
                    {s.drug}
                    {s.potency && (
                      <span className="text-slate-400"> ({s.potency})</span>
                    )}
                  </span>
                ))}
              </Bucket>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Bucket({
  label,
  color,
  children,
}: {
  label: string;
  color: "blue" | "red" | "amber";
  children: React.ReactNode[];
}) {
  const colorMap = {
    blue: "bg-blue-50 text-blue-700",
    red: "bg-red-50 text-red-700",
    amber: "bg-amber-50 text-amber-700",
  };

  if (children.length === 0) return null;

  return (
    <div className="mt-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <div className="mt-0.5 flex flex-wrap gap-1">
        {children.map((child, i) => (
          <span
            key={i}
            className={`inline-block rounded px-1.5 py-0.5 text-xs ${colorMap[color]}`}
          >
            {child}
          </span>
        ))}
      </div>
    </div>
  );
}
