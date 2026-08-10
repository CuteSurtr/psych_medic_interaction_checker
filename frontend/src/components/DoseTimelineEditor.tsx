import { useState } from "react";
import type { DoseEventInput, RegimenItem } from "../types";

interface Props {
  events: DoseEventInput[];
  onChange: (events: DoseEventInput[]) => void;
  medications: RegimenItem[];
}

const EVENT_TYPES: DoseEventInput["event_type"][] = [
  "start",
  "dose_change",
  "stop",
];

const FREQUENCIES: { value: string; label: string }[] = [
  { value: "daily", label: "Once daily" },
  { value: "BID", label: "Twice daily (BID)" },
  { value: "TID", label: "Three times daily (TID)" },
  { value: "QHS", label: "At bedtime (QHS)" },
];

export default function DoseTimelineEditor({
  events,
  onChange,
  medications,
}: Props) {
  const [medId, setMedId] = useState<number | "">(
    medications.length > 0 ? medications[0].id : ""
  );
  const [eventType, setEventType] =
    useState<DoseEventInput["event_type"]>("start");
  const [day, setDay] = useState(1);
  const [doseMg, setDoseMg] = useState(0);
  const [frequency, setFrequency] = useState(FREQUENCIES[0].value);

  const addEvent = () => {
    if (medId === "") return;
    const med = medications.find((m) => m.id === medId);
    if (!med) return;
    const newEvent: DoseEventInput = {
      medication_id: med.id,
      medication_name: med.generic_name,
      event_type: eventType,
      event_day: day,
      dose_mg: doseMg,
      frequency,
    };
    onChange([...events, newEvent]);
  };

  const removeEvent = (index: number) => {
    onChange(events.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      <fieldset className="rounded-lg border border-slate-200 bg-white p-4">
        <legend className="px-2 text-sm font-semibold text-slate-700">
          Add Dose Event
        </legend>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div>
            <label
              htmlFor="dte-med"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Medication
            </label>
            <select
              id="dte-med"
              value={medId}
              onChange={(e) =>
                setMedId(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm
                         focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
            >
              {medications.length === 0 && (
                <option value="">No medications</option>
              )}
              {medications.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.generic_name}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="dte-type"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Event Type
            </label>
            <select
              id="dte-type"
              value={eventType}
              onChange={(e) =>
                setEventType(e.target.value as DoseEventInput["event_type"])
              }
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm
                         focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
            >
              {EVENT_TYPES.map((t) => (
                <option key={t} value={t}>
                  {t.replace("_", " ")}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label
              htmlFor="dte-day"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Day
            </label>
            <input
              id="dte-day"
              type="number"
              min={1}
              value={day}
              onChange={(e) => setDay(Number(e.target.value) || 1)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm
                         focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
            />
          </div>

          <div>
            <label
              htmlFor="dte-dose"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Dose (mg)
            </label>
            <input
              id="dte-dose"
              type="number"
              min={0}
              step="any"
              value={doseMg}
              onChange={(e) => setDoseMg(Number(e.target.value) || 0)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm
                         focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
            />
          </div>

          <div>
            <label
              htmlFor="dte-freq"
              className="block text-xs font-medium text-slate-600 mb-1"
            >
              Frequency
            </label>
            <select
              id="dte-freq"
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              className="w-full rounded border border-slate-300 px-2 py-1.5 text-sm
                         focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-400/30"
            >
              {FREQUENCIES.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-end">
            <button
              type="button"
              disabled={medId === "" || medications.length === 0}
              onClick={addEvent}
              className="w-full rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white
                         hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition"
            >
              Add
            </button>
          </div>
        </div>
      </fieldset>

      {events.length > 0 && (
        <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white text-sm">
          {events.map((ev, idx) => (
            <li key={idx} className="flex items-center gap-3 px-4 py-2.5">
              <span className="flex-1 text-slate-700">
                <span className="font-medium">{ev.medication_name}</span>{" "}
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">
                  {ev.event_type.replace("_", " ")}
                </span>{" "}
                Day {ev.event_day} · {ev.dose_mg} mg · {ev.frequency}
              </span>
              <button
                type="button"
                aria-label={`Remove event ${idx + 1}`}
                onClick={() => removeEvent(idx)}
                className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-500 transition"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-4 w-4"
                  viewBox="0 0 20 20"
                  fill="currentColor"
                >
                  <path
                    fillRule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
