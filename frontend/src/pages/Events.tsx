/* Events-Seite: Neue Events anlegen + Spielzeiten verwalten */

import { useState, useEffect } from "react";
import { seasonsAPI, eventsAPI, projectsAPI } from "../api/client";
import Badge from "../components/common/Badge";
import type { Season, SBPEvent, Project, ValidationResult } from "../types";
import { DIENST_TYPES, FORMATIONS, STATUS_OPTIONS } from "../types";

function formatDate(s: string): string {
  return new Date(s).toLocaleDateString("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric" });
}

export default function Events() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [activeSeason, setActiveSeason] = useState<Season | null>(null);
  const [events, setEvents] = useState<SBPEvent[]>([]);
  const [showNewSeason, setShowNewSeason] = useState(false);
  const [showNewEvent, setShowNewEvent] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);

  // Season-Form
  const [sName, setSName] = useState("");
  const [sStart, setSStart] = useState("");
  const [sEnd, setSEnd] = useState("");

  // Event-Form
  const [evDate, setEvDate] = useState("");
  const [evStartTime, setEvStartTime] = useState("");
  const [evEndTime, setEvEndTime] = useState("");
  const [evType, setEvType] = useState("Probe");
  const [evFormation, setEvFormation] = useState("SBP");
  const [evStatus, setEvStatus] = useState<"fest" | "geplant" | "moeglich">("geplant");
  const [evProgramm, setEvProgramm] = useState("");
  const [evOrt, setEvOrt] = useState("");
  const [evLeitung, setEvLeitung] = useState("");
  const [evKleidung, setEvKleidung] = useState("");
  const [evSonstiges, setEvSonstiges] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    loadSeasons();
  }, []);

  useEffect(() => {
    if (activeSeason) loadEvents();
  }, [activeSeason]);

  async function loadSeasons() {
    const res = await seasonsAPI.list();
    const s = res.data as Season[];
    setSeasons(s);
    setActiveSeason(s.find((x) => x.is_active) || s[0] || null);
  }

  async function loadEvents() {
    if (!activeSeason) return;
    const res = await eventsAPI.list({ season_id: activeSeason.id });
    setEvents(res.data as SBPEvent[]);
  }

  async function createSeason() {
    await seasonsAPI.create({ name: sName, start_date: sStart, end_date: sEnd, is_active: true });
    setShowNewSeason(false);
    setSName(""); setSStart(""); setSEnd("");
    loadSeasons();
  }

  // Echtzeit-TVK-Validierung
  async function validateEvent() {
    if (!activeSeason || !evDate) return;
    try {
      const res = await eventsAPI.validate({
        season_id: activeSeason.id,
        event_date: evDate,
        start_time: evStartTime || undefined,
        end_time: evEndTime || undefined,
        dienst_type: evType,
        formation: evFormation,
        status: evStatus,
      });
      setValidation(res.data.validation as ValidationResult);
    } catch {
      setValidation(null);
    }
  }

  // Validierung bei Datums-/Zeitaenderung
  useEffect(() => {
    const timer = setTimeout(validateEvent, 500);
    return () => clearTimeout(timer);
  }, [evDate, evStartTime, evEndTime, evType]);

  async function createEvent() {
    if (!activeSeason) return;
    setSaving(true);
    try {
      await eventsAPI.create({
        season_id: activeSeason.id,
        event_date: evDate,
        start_time: evStartTime || undefined,
        end_time: evEndTime || undefined,
        dienst_type: evType,
        formation: evFormation,
        status: evStatus,
        programm: evProgramm,
        ort: evOrt,
        leitung: evLeitung,
        kleidung: evKleidung,
        sonstiges: evSonstiges,
      });
      setShowNewEvent(false);
      resetEventForm();
      loadEvents();
    } finally {
      setSaving(false);
    }
  }

  function resetEventForm() {
    setEvDate(""); setEvStartTime(""); setEvEndTime("");
    setEvType("Probe"); setEvFormation("SBP"); setEvStatus("geplant");
    setEvProgramm(""); setEvOrt(""); setEvLeitung(""); setEvKleidung(""); setEvSonstiges("");
    setValidation(null);
  }

  async function deleteEvent(id: number) {
    await eventsAPI.delete(id);
    loadEvents();
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Events & Spielzeiten</h1>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowNewSeason(true)} className="btn-pill border border-[var(--color-border)] text-sm">
            + Spielzeit
          </button>
          <button onClick={() => setShowNewEvent(true)} className="btn-pill btn-primary text-sm" disabled={!activeSeason}>
            + Event
          </button>
        </div>
      </div>

      {/* Spielzeit-Picker */}
      {seasons.length > 0 && (
        <div className="flex gap-2 mb-6">
          {seasons.map((s) => (
            <button
              key={s.id}
              onClick={() => setActiveSeason(s)}
              className={`btn-pill text-sm ${activeSeason?.id === s.id ? "btn-primary" : "border border-[var(--color-border)]"}`}
            >
              {s.name} ({s.event_count})
            </button>
          ))}
        </div>
      )}

      {/* Neue Spielzeit Modal */}
      {showNewSeason && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50" onClick={() => setShowNewSeason(false)}>
          <div className="card p-6 max-w-sm w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-medium mb-4">Neue Spielzeit</h3>
            <div className="space-y-3">
              <input placeholder="Name (z.B. 2027)" value={sName} onChange={(e) => setSName(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
              <div className="grid grid-cols-2 gap-2">
                <input type="date" value={sStart} onChange={(e) => setSStart(e.target.value)} className="px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
                <input type="date" value={sEnd} onChange={(e) => setSEnd(e.target.value)} className="px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
              </div>
              <button onClick={createSeason} className="w-full btn-pill btn-primary">Anlegen</button>
            </div>
          </div>
        </div>
      )}

      {/* Neues Event Modal */}
      {showNewEvent && (
        <div className="fixed inset-0 bg-black/20 flex items-start justify-center z-50 pt-20 overflow-y-auto" onClick={() => { setShowNewEvent(false); resetEventForm(); }}>
          <div className="card p-6 max-w-lg w-full mx-4 mb-20" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-medium mb-4">Neues Event</h3>

            {/* TVK-Validierung */}
            {validation && (
              <div className={`mb-4 p-3 rounded-lg text-sm ${
                validation.status === "error" ? "bg-red-50 border border-red-200" :
                validation.status === "warning" ? "bg-yellow-50 border border-yellow-200" :
                "bg-green-50 border border-green-200"
              }`}>
                <div className="flex items-center gap-2 mb-1">
                  <span>{validation.status === "ok" ? "✓" : validation.status === "warning" ? "⚠" : "✕"}</span>
                  <span className="font-medium">
                    KW {validation.week_start?.slice(5, 10)} — {validation.total_dienste}/{validation.max_dienste} Dienste
                  </span>
                </div>
                {validation.violations.map((v, i) => (
                  <div key={i} className="text-xs mt-1">
                    <Badge label={v.severity} variant="severity" value={v.severity} />
                    <span className="ml-1">{v.message}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="space-y-3">
              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs text-[var(--color-secondary)] mb-1">Datum *</label>
                  <input type="date" value={evDate} onChange={(e) => setEvDate(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" required />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-secondary)] mb-1">Von</label>
                  <input type="time" value={evStartTime} onChange={(e) => setEvStartTime(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-secondary)] mb-1">Bis</label>
                  <input type="time" value={evEndTime} onChange={(e) => setEvEndTime(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div>
                  <label className="block text-xs text-[var(--color-secondary)] mb-1">Typ</label>
                  <select value={evType} onChange={(e) => setEvType(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg">
                    {DIENST_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-secondary)] mb-1">Formation</label>
                  <select value={evFormation} onChange={(e) => setEvFormation(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg">
                    {FORMATIONS.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-[var(--color-secondary)] mb-1">Status</label>
                  <select value={evStatus} onChange={(e) => setEvStatus(e.target.value as typeof evStatus)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg">
                    {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              </div>

              <input placeholder="Programm / Beschreibung" value={evProgramm} onChange={(e) => setEvProgramm(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
              <div className="grid grid-cols-2 gap-2">
                <input placeholder="Ort" value={evOrt} onChange={(e) => setEvOrt(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
                <input placeholder="Leitung / Dirigent" value={evLeitung} onChange={(e) => setEvLeitung(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <input placeholder="Kleidung" value={evKleidung} onChange={(e) => setEvKleidung(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
                <input placeholder="Sonstiges" value={evSonstiges} onChange={(e) => setEvSonstiges(e.target.value)} className="w-full px-3 py-2 text-sm border border-[var(--color-border)] rounded-lg" />
              </div>

              <button onClick={createEvent} disabled={saving || !evDate} className="w-full btn-pill btn-primary disabled:opacity-50">
                {saving ? "Speichern..." : "Event anlegen"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Event-Liste */}
      <div className="space-y-2">
        {events.length === 0 && activeSeason && (
          <div className="card p-8 text-center text-[var(--color-secondary)]">
            Noch keine Events in dieser Spielzeit.
          </div>
        )}
        {events.map((ev) => (
          <div key={ev.id} className="card p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-sm font-medium w-24">{formatDate(ev.event_date)}</div>
              <div className="flex gap-1">
                <Badge label={ev.formation} variant="formation" value={ev.formation} />
                <Badge label={ev.status} variant="status" value={ev.status} />
              </div>
              <div className="text-sm text-[var(--color-primary)]">
                {ev.dienst_type}{ev.start_time ? ` ${ev.start_time}` : ""}{ev.end_time ? `–${ev.end_time}` : ""}
              </div>
              <div className="text-sm text-[var(--color-secondary)]">
                {ev.programm || ev.ort || ""}
              </div>
            </div>
            <button onClick={() => deleteEvent(ev.id)} className="text-xs text-[var(--color-error)] hover:underline">
              Löschen
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
