/* Generator-Seite: Dienstplan aus DB-Events generieren */

import { useState, useEffect } from "react";
import { seasonsAPI, generatorAPI } from "../api/client";
import type { Season, GeneratedPlan } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "";

export default function Generator() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [seasonId, setSeasonId] = useState<number | null>(null);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [generating, setGenerating] = useState(false);
  const [plans, setPlans] = useState<GeneratedPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<GeneratedPlan | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    seasonsAPI.list().then((res) => {
      const s = res.data as Season[];
      setSeasons(s);
      const active = s.find((x) => x.is_active);
      if (active) {
        setSeasonId(active.id);
        setStartDate(active.start_date);
        setEndDate(active.end_date);
      }
    });
    loadPlans();
  }, []);

  async function loadPlans() {
    const res = await generatorAPI.plans();
    setPlans(res.data as GeneratedPlan[]);
  }

  async function generate() {
    if (!seasonId || !startDate || !endDate) return;
    setGenerating(true);
    setError("");
    try {
      const res = await generatorAPI.generate({
        season_id: seasonId,
        start_date: startDate,
        end_date: endDate,
      });
      await loadPlans();
      // Neuesten Plan laden
      const plan = res.data.plan as GeneratedPlan;
      const detailRes = await generatorAPI.plan(plan.id);
      setSelectedPlan(detailRes.data as GeneratedPlan);
    } catch (err: unknown) {
      setError((err as { response?: { data?: { error?: string } } })?.response?.data?.error || "Generierung fehlgeschlagen.");
    } finally {
      setGenerating(false);
    }
  }

  async function viewPlan(id: number) {
    const res = await generatorAPI.plan(id);
    setSelectedPlan(res.data as GeneratedPlan);
  }

  const token = localStorage.getItem("sbp_token");

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <h1 className="text-2xl font-semibold tracking-tight mb-6">Dienstplan generieren</h1>

      {/* Generator-Formular */}
      <div className="card p-6 mb-6">
        <div className="grid grid-cols-4 gap-4 items-end">
          <div>
            <label className="block text-xs text-[var(--color-secondary)] mb-1">Spielzeit</label>
            <select
              value={seasonId || ""}
              onChange={(e) => {
                const id = Number(e.target.value);
                setSeasonId(id);
                const s = seasons.find((x) => x.id === id);
                if (s) { setStartDate(s.start_date); setEndDate(s.end_date); }
              }}
              className="w-full px-3 py-2.5 text-sm border border-[var(--color-border)] rounded-lg"
            >
              {seasons.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-[var(--color-secondary)] mb-1">Von</label>
            <input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} className="w-full px-3 py-2.5 text-sm border border-[var(--color-border)] rounded-lg" />
          </div>
          <div>
            <label className="block text-xs text-[var(--color-secondary)] mb-1">Bis</label>
            <input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} className="w-full px-3 py-2.5 text-sm border border-[var(--color-border)] rounded-lg" />
          </div>
          <button onClick={generate} disabled={generating || !seasonId} className="btn-pill btn-primary py-2.5 text-sm disabled:opacity-50">
            {generating ? "Generiere..." : "Dienstplan generieren"}
          </button>
        </div>
        {error && <p className="text-sm text-[var(--color-error)] mt-3">{error}</p>}
      </div>

      {/* Ausgewaehlter Plan — Details */}
      {selectedPlan && (
        <div className="card p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">
              Dienstplan {selectedPlan.plan_start} — {selectedPlan.plan_end}
            </h2>
            <span className={`text-xs px-2 py-1 rounded-full ${
              selectedPlan.status === "ready" ? "bg-green-100 text-green-700" :
              selectedPlan.status === "error" ? "bg-red-100 text-red-700" :
              "bg-yellow-100 text-yellow-700"
            }`}>
              {selectedPlan.status}
            </span>
          </div>

          {/* Downloads */}
          {selectedPlan.status === "ready" && (
            <div className="flex gap-3 mb-6">
              {selectedPlan.has_collective_docx && (
                <a
                  href={`${API_BASE}/api/generator/plans/${selectedPlan.id}/collective.docx`}
                  className="btn-pill btn-primary text-sm"
                  target="_blank"
                >
                  📄 Gesamtplan (Word)
                </a>
              )}
              <a
                href={`${API_BASE}/api/generator/plans/${selectedPlan.id}/collective.pdf`}
                className="btn-pill border border-[var(--color-border)] text-sm"
                target="_blank"
              >
                📄 Gesamtplan (PDF)
              </a>
            </div>
          )}

          {/* Individuelle Plaene */}
          {selectedPlan.individual_plans && selectedPlan.individual_plans.length > 0 && (
            <div>
              <h3 className="text-sm font-medium text-[var(--color-secondary)] mb-3">
                {selectedPlan.individual_plans.length} Einzelpläne
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {selectedPlan.individual_plans.map((ip) => (
                  <div key={ip.id} className="flex items-center justify-between p-2 bg-[var(--color-bg)] rounded-lg">
                    <span className={`text-sm ${ip.is_vakant ? "text-[var(--color-secondary)] italic" : ""}`}>
                      {ip.display_name}
                    </span>
                    <div className="flex gap-1">
                      {ip.has_docx && (
                        <a
                          href={`${API_BASE}/api/musicians/plans/${ip.id}/individual.pdf`}
                          className="text-xs text-[var(--color-accent)] hover:underline"
                          target="_blank"
                        >
                          PDF
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Fruehere Plaene */}
      {plans.length > 0 && (
        <div>
          <h2 className="text-lg font-medium mb-3">Generierte Pläne</h2>
          <div className="space-y-2">
            {plans.map((p) => (
              <button
                key={p.id}
                onClick={() => viewPlan(p.id)}
                className={`card p-4 w-full text-left flex items-center justify-between ${
                  selectedPlan?.id === p.id ? "ring-2 ring-[var(--color-accent)]" : ""
                }`}
              >
                <div>
                  <span className="text-sm font-medium">{p.plan_start} — {p.plan_end}</span>
                  <span className="text-xs text-[var(--color-secondary)] ml-3">
                    {p.individual_count} Einzelpläne
                  </span>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  p.status === "ready" ? "bg-green-100 text-green-700" : "bg-yellow-100 text-yellow-700"
                }`}>
                  {p.status}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
