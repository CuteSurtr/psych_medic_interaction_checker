import type { InteractionRow, RegimenItem } from "../types";
import { getDrugClassColor, SEVERITY_COLORS } from "./colorSchemes";

/** Hex fill/stroke color for a medication node from its drug class string. */
export function drugClassColor(drugClass: string): string {
  return getDrugClassColor(drugClass);
}

export function severityStroke(sev: string): { stroke: string; dash: string; width: number } {
  const key = sev.toLowerCase();
  switch (key) {
    case "critical":
      return { stroke: SEVERITY_COLORS.critical, dash: "0", width: 4 };
    case "major":
      return { stroke: SEVERITY_COLORS.major, dash: "0", width: 2.5 };
    case "moderate":
      return { stroke: SEVERITY_COLORS.moderate, dash: "8 4", width: 2 };
    case "minor":
      return { stroke: SEVERITY_COLORS.minor, dash: "2 4", width: 1 };
    default:
      return { stroke: SEVERITY_COLORS.minor, dash: "2 4", width: 1 };
  }
}

const SEVERITY_RANK: Record<string, number> = {
  critical: 0,
  major: 1,
  moderate: 2,
  minor: 3,
  safe: 4,
};

function severityOrder(severity: string): number {
  const k = severity.toLowerCase();
  return SEVERITY_RANK[k] ?? 50;
}

function pairKey(a: number, b: number): string {
  return a < b ? `${a}:${b}` : `${b}:${a}`;
}

export interface GraphInteractionLink {
  drug_a_id: number;
  drug_b_id: number;
  severity: string;
  stroke: { stroke: string; dash: string; width: number };
  row: InteractionRow;
}

/** One link per unordered drug pair, using the worst severity among matching interactions. */
export function buildGraphLinks(
  regimen: RegimenItem[],
  interactions: InteractionRow[]
): GraphInteractionLink[] {
  const ids = new Set(regimen.map((m) => m.id));
  const byPair = new Map<string, InteractionRow[]>();

  for (const row of interactions) {
    if (!ids.has(row.drug_a_id) || !ids.has(row.drug_b_id)) continue;
    const key = pairKey(row.drug_a_id, row.drug_b_id);
    const list = byPair.get(key);
    if (list) list.push(row);
    else byPair.set(key, [row]);
  }

  const links: GraphInteractionLink[] = [];
  for (const rows of byPair.values()) {
    let best = rows[0];
    for (let i = 1; i < rows.length; i++) {
      const r = rows[i];
      if (severityOrder(r.severity) < severityOrder(best.severity)) best = r;
    }
    const a = Math.min(best.drug_a_id, best.drug_b_id);
    const b = Math.max(best.drug_a_id, best.drug_b_id);
    links.push({
      drug_a_id: a,
      drug_b_id: b,
      severity: best.severity,
      stroke: severityStroke(best.severity),
      row: best,
    });
  }
  return links;
}
