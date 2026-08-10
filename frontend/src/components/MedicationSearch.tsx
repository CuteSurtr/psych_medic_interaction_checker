import { useCallback, useEffect, useRef, useState } from "react";
import type { MedicationSearchHit } from "../types";
import { apiUrl } from "../utils/api";

interface Props {
  onSelect: (m: MedicationSearchHit) => void;
}

export default function MedicationSearch({ onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<MedicationSearchHit[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLUListElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const fetchResults = useCallback(async (q: string) => {
    if (q.trim().length < 2) {
      setResults([]);
      setOpen(false);
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const res = await fetch(
        apiUrl(`/api/medications/search?q=${encodeURIComponent(q)}`),
        { signal: controller.signal }
      );
      if (!res.ok) throw new Error(res.statusText);
      const data: MedicationSearchHit[] = await res.json();
      setResults(data);
      setOpen(data.length > 0);
      setActiveIndex(-1);
    } catch (err) {
      if ((err as DOMException).name !== "AbortError") {
        setResults([]);
        setOpen(false);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => fetchResults(query), 200);
    return () => clearTimeout(timer);
  }, [query, fetchResults]);

  const select = (hit: MedicationSearchHit) => {
    onSelect(hit);
    setQuery("");
    setResults([]);
    setOpen(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return;
    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, results.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0 && activeIndex < results.length) {
          select(results[activeIndex]);
        }
        break;
      case "Escape":
        setOpen(false);
        setActiveIndex(-1);
        break;
    }
  };

  useEffect(() => {
    if (activeIndex >= 0 && listRef.current) {
      const el = listRef.current.children[activeIndex] as HTMLElement | undefined;
      el?.scrollIntoView({ block: "nearest" });
    }
  }, [activeIndex]);

  return (
    <div className="relative w-full">
      <label
        htmlFor="med-search"
        className="block text-sm font-medium text-slate-700 mb-1"
      >
        Search medications
      </label>
      <div className="relative">
        <input
          ref={inputRef}
          id="med-search"
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls="med-search-listbox"
          aria-activedescendant={
            activeIndex >= 0 ? `med-option-${activeIndex}` : undefined
          }
          className="w-full rounded-lg border border-slate-300 bg-white px-4 py-2.5 text-sm
                     shadow-sm placeholder:text-slate-400
                     focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20
                     transition"
          placeholder="Type a medication name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
          onFocus={() => results.length > 0 && setOpen(true)}
        />
        {loading && (
          <span className="absolute right-3 top-1/2 -translate-y-1/2">
            <svg
              className="h-4 w-4 animate-spin text-indigo-500"
              viewBox="0 0 24 24"
              fill="none"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
              />
            </svg>
          </span>
        )}
      </div>

      {open && (
        <ul
          ref={listRef}
          id="med-search-listbox"
          role="listbox"
          className="absolute z-30 mt-1 max-h-64 w-full overflow-auto rounded-lg border border-slate-200
                     bg-white shadow-lg"
        >
          {results.map((hit, idx) => (
            <li
              key={hit.id}
              id={`med-option-${idx}`}
              role="option"
              aria-selected={idx === activeIndex}
              className={`cursor-pointer px-4 py-2.5 text-sm transition
                ${idx === activeIndex ? "bg-indigo-50 text-indigo-900" : "text-slate-700 hover:bg-slate-50"}`}
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => select(hit)}
              onMouseEnter={() => setActiveIndex(idx)}
            >
              <span className="font-medium">{hit.generic_name}</span>
              {hit.brand_names.length > 0 && (
                <span className="ml-2 text-xs text-slate-400">
                  ({hit.brand_names.join(", ")})
                </span>
              )}
              <span className="ml-2 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                {hit.drug_class}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
