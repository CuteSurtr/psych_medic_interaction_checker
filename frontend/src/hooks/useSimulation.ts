import { useCallback, useState } from "react";
import type { SimulationResult } from "../types";
import { apiUrl } from "../utils/api";

export function useSimulation() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);

  // Single request: the API configures and runs the simulation in one call, so
  // nothing has to persist between two round trips. That is what lets the
  // backend run on serverless without a database.
  const createAndRun = useCallback(async (body: Record<string, unknown>): Promise<SimulationResult | null> => {
    setLoading(true);
    try {
      const res = await fetch(apiUrl("/api/simulation/run"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        setResult(null);
        return null;
      }
      const data = (await res.json()) as SimulationResult;
      setResult(data);
      return data;
    } catch {
      setResult(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { createAndRun, result, loading };
}
