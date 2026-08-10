export const SEVERITY_COLORS: Record<string, string> = {
  critical: "#DC2626",
  major: "#EA580C",
  moderate: "#CA8A04",
  minor: "#6B7280",
  safe: "#16A34A",
};

export const DRUG_CLASS_COLORS: Record<string, string> = {
  SSRI: "#3B82F6",
  SNRI: "#6366F1",
  TCA: "#8B5CF6",
  MAOI: "#DC2626",
  "Atypical antipsychotic": "#A855F7",
  "Typical antipsychotic": "#7C3AED",
  Benzodiazepine: "#10B981",
  "Mood stabilizer": "#F59E0B",
  Stimulant: "#EF4444",
  NDRI: "#0EA5E9",
  NaSSA: "#06B6D4",
  Opioid: "#BE123C",
  default: "#6B7280",
};

export function getDrugClassColor(cls: string): string {
  const upper = cls.toUpperCase();
  for (const [key, value] of Object.entries(DRUG_CLASS_COLORS)) {
    if (upper.includes(key.toUpperCase())) return value;
  }
  return DRUG_CLASS_COLORS.default;
}
