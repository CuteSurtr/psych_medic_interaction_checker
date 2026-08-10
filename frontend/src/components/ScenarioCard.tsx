interface Props {
  scenario: { id: number; name: string; description: string };
  onLoad: (id: number) => void;
}

export default function ScenarioCard({ scenario, onLoad }: Props) {
  return (
    <div className="flex flex-col justify-between rounded-lg border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md">
      <div>
        <h3 className="text-sm font-semibold text-slate-800">
          {scenario.name}
        </h3>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">
          {scenario.description}
        </p>
      </div>
      <button
        type="button"
        onClick={() => onLoad(scenario.id)}
        className="mt-4 self-start rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-medium text-white
                   hover:bg-indigo-700 transition"
      >
        Load scenario
      </button>
    </div>
  );
}
