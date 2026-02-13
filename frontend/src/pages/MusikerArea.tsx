/* Musiker-Bereich: Alphabetische Liste + PDF-Downloads */

import { useState, useEffect, useMemo } from "react";
import { musiciansAPI } from "../api/client";

const API_BASE = import.meta.env.VITE_API_URL || "";

interface MusicianEntry {
  id: number;
  display_name: string;
  is_vakant: boolean;
  has_individual_pdf: boolean;
}

interface DirectoryResponse {
  musicians: MusicianEntry[];
  plan: {
    id: number;
    plan_start: string;
    plan_end: string;
  } | null;
}

export default function MusikerArea() {
  const [data, setData] = useState<DirectoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterLetter, setFilterLetter] = useState("");

  useEffect(() => {
    setLoading(true);
    musiciansAPI.directory()
      .then((res) => setData(res.data as DirectoryResponse))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Buchstaben-Navigation
  const letters = useMemo(() => {
    if (!data) return [];
    const set = new Set<string>();
    data.musicians.forEach((m) => {
      if (!m.is_vakant) {
        const nachname = m.display_name.split(" ").pop() || "";
        if (nachname[0]) set.add(nachname[0].toUpperCase());
      }
    });
    return Array.from(set).sort();
  }, [data]);

  const filteredMusicians = useMemo(() => {
    if (!data) return [];
    if (!filterLetter) return data.musicians;
    if (filterLetter === "V") return data.musicians.filter((m) => m.is_vakant);
    return data.musicians.filter((m) => {
      if (m.is_vakant) return false;
      const nachname = m.display_name.split(" ").pop() || "";
      return nachname[0]?.toUpperCase() === filterLetter;
    });
  }, [data, filterLetter]);

  if (loading) {
    return <div className="flex items-center justify-center h-96 text-[var(--color-secondary)]">Lade...</div>;
  }

  if (!data || !data.plan) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-12 text-center">
        <div className="card p-12">
          <p className="text-[var(--color-secondary)]">Noch kein Dienstplan generiert.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Dienstpläne</h1>
        <p className="text-sm text-[var(--color-secondary)] mt-0.5">
          Zeitraum: {data.plan.plan_start} — {data.plan.plan_end}
        </p>
      </div>

      {/* Buchstaben-Navigation */}
      <div className="flex flex-wrap gap-1 mb-6">
        <button
          onClick={() => setFilterLetter("")}
          className={`btn-pill text-xs ${!filterLetter ? "btn-primary" : "border border-[var(--color-border)]"}`}
        >
          Alle
        </button>
        {letters.map((l) => (
          <button
            key={l}
            onClick={() => setFilterLetter(l)}
            className={`btn-pill text-xs ${filterLetter === l ? "btn-primary" : "border border-[var(--color-border)]"}`}
          >
            {l}
          </button>
        ))}
        <button
          onClick={() => setFilterLetter("V")}
          className={`btn-pill text-xs ${filterLetter === "V" ? "btn-primary" : "border border-[var(--color-border)]"}`}
        >
          Vakant
        </button>
      </div>

      {/* Musiker-Liste */}
      <div className="space-y-2">
        {filteredMusicians.map((m) => (
          <div key={m.id} className="card p-4 flex items-center justify-between">
            <span className={`text-sm font-medium ${m.is_vakant ? "text-[var(--color-secondary)] italic" : ""}`}>
              {m.display_name}
            </span>
            <div className="flex items-center gap-2">
              {m.has_individual_pdf && (
                <>
                  <a
                    href={`${API_BASE}/api/musicians/plans/${m.id}/individual.pdf`}
                    className="btn-pill text-xs btn-primary"
                    target="_blank"
                  >
                    Einzelplan (PDF)
                  </a>
                  <a
                    href={`${API_BASE}/api/musicians/plans/${m.id}/collective.pdf`}
                    className="btn-pill text-xs border border-[var(--color-border)]"
                    target="_blank"
                  >
                    Gesamtplan
                  </a>
                </>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
