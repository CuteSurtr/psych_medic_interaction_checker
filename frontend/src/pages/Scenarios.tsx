import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { ScenarioTemplate } from "../types";
import { apiUrl } from "../utils/api";
import AppHeader from "../components/AppHeader";
import ScenarioCard from "../components/ScenarioCard";
import DisclaimerFooter from "../components/DisclaimerFooter";

export default function Scenarios() {
  const [templates, setTemplates] = useState<ScenarioTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(apiUrl("/api/simulation/templates"))
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: ScenarioTemplate[]) => {
        if (!cancelled) setTemplates(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load scenarios");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const navigate = useNavigate();

  const handleLoad = (id: number) => {
    navigate(`/simulator?scenario=${id}`);
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-50 font-sans">
      <AppHeader title="Clinical Scenarios" />

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
        {loading && (
          <div className="flex h-40 items-center justify-center text-sm text-slate-400">
            Loading scenarios…
          </div>
        )}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && templates.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-400">
            No clinical scenarios available.
          </div>
        )}

        {!loading && templates.length > 0 && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((t) => (
              <ScenarioCard key={t.id} scenario={t} onLoad={handleLoad} />
            ))}
          </div>
        )}
      </main>

      <DisclaimerFooter />
    </div>
  );
}
