import { useCallback, useState } from "react";
import type { MedicationSearchHit } from "../types";
import { apiUrl } from "../utils/api";

export function useMedicationSearch() {
  const [loading, setLoading] = useState(false);
  const search = useCallback(async (q: string): Promise<MedicationSearchHit[]> => {
    if (q.trim().length < 2) return [];
    setLoading(true);
    try {
      const r = await fetch(apiUrl(`/api/medications/search?q=${encodeURIComponent(q.trim())}`));
      const data: unknown = await r.json();
      return Array.isArray(data) ? (data as MedicationSearchHit[]) : [];
    } finally {
      setLoading(false);
    }
  }, []);
  return { search, loading };
}
