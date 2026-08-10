import { useCallback, useState } from "react";
import type { InteractionRow } from "../types";
import { apiUrl } from "../utils/api";

export function useInteractionCheck() {
  const [loading, setLoading] = useState(false);
  const check = useCallback(
    async (medicationIds: number[], cyp2d6 = "normal", cyp2c19 = "normal"): Promise<InteractionRow[]> => {
      setLoading(true);
      try {
        const r = await fetch(apiUrl("/api/interactions/check"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            medication_ids: medicationIds,
            cyp2d6_phenotype: cyp2d6,
            cyp2c19_phenotype: cyp2c19,
          }),
        });
        const data = (await r.json()) as { interactions?: InteractionRow[] };
        return data.interactions ?? [];
      } finally {
        setLoading(false);
      }
    },
    []
  );
  return { check, loading };
}
