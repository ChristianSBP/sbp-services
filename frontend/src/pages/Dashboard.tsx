/* Dashboard — Jahresplan-Hauptansicht mit Timeline und Auslastung */

import { useState, useEffect, useMemo } from "react";
import { seasonsAPI, eventsAPI } from "../api/client";
import Badge from "../components/common/Badge";
import type { Season, SBPEvent } from "../types";
import { FORMATION_COLORS, STATUS_COLORS } from "../types";
import type { EventStatus } from "../types";

/* Hilfsfunktionen */
function getWeekNumber(d: Date): number {
  const date = new Date(d.getTime());
  date.setHours(0, 0, 0, 0);
  date.setDate(date.getDate() + 3 - ((date.getDay() + 6) % 7));
  const week1 = new Date(date.getFullYear(), 0, 4);
  return 1 + Math.round(((date.getTime() - week1.getTime()) / 86400000 - 3 + ((week1.getDay() + 6) % 7)) / 7);
}

function getMonday(d: Date): Date {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(date.setDate(diff));
}

function formatDate(s: string): string {
  const d = new Date(s);
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
}

const MONTH_NAMES = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"];

/* Timeline-Gruppen (Y-Achse) */
const FORMATION_GROUPS = [
  { key: "SBP", label: "SBP (Tutti)" },
  { key: "Brass", label: "Brass" },
  { key: "BLQ", label: "BLQ" },
  { key: "KLQ", label: "KLQ" },
  { key: "SBQ", label: "SBQ" },
  { key: "Serenaden", label: "Serenaden" },
  { key: "Sonstige", label: "Sonstige" },
];

function getFormationGroup(formation: string): string {
  if (formation === "SBP" || formation === "Unbekannt") return "SBP";
  if (formation.includes("Brass") || formation === "Blech") return "Brass";
  if (formation === "BLQ") return "BLQ";
  if (formation === "KLQ") return "KLQ";
  if (formation === "SBQ") return "SBQ";
  if (formation === "Serenaden") return "Serenaden";
  return "Sonstige";
}

export default function Dashboard() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [activeSeason, setActiveSeason] = useState<Season | null>(null);
  const [events, setEvents] = useState<SBPEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterFormation, setFilterFormation] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [selectedEvent, setSelectedEvent] = useState<SBPEvent | null>(null);

  // Daten laden
  useEffect(() => {
    setLoading(true);
    seasonsAPI.list().then((res) => {
      const s = res.data as Season[];
      setSeasons(s);
      const active = s.find((x) => x.is_active) || s[0];
      if (active) setActiveSeason(active);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeSeason) return;
    eventsAPI.list({ season_id: activeSeason.id }).then((res) => {
      setEvents(res.data as SBPEvent[]);
    }).catch(() => {});
  }, [activeSeason]);

  // Events nach Filter
  const filteredEvents = useMemo(() => {
    let result = events;
    if (filterFormation) result = result.filter((e) => getFormationGroup(e.formation) === filterFormation);
    if (filterStatus) result = result.filter((e) => e.status === filterStatus);
    return result;
  }, [events, filterFormation, filterStatus]);

  // Wochen berechnen
  const weeks = useMemo(() => {
    if (!activeSeason) return [];
    const start = getMonday(new Date(activeSeason.start_date));
    const end = new Date(activeSeason.end_date);
    const result: Date[] = [];
    const current = new Date(start);
    while (current <= end) {
      result.push(new Date(current));
      current.setDate(current.getDate() + 7);
    }
    return result;
  }, [activeSeason]);

  // Dienste pro Woche berechnen (vereinfacht: Anzahl Events)
  const weeklyLoad = useMemo(() => {
    const map = new Map<string, number>();
    for (const e of events) {
      const monday = getMonday(new Date(e.event_date));
      const key = monday.toISOString().slice(0, 10);
      map.set(key, (map.get(key) || 0) + 1);
    }
    return map;
  }, [events]);

  // Quick-Stats
  const stats = useMemo(() => {
    const total = events.length;
    const fest = events.filter((e) => e.status === "fest").length;
    const geplant = events.filter((e) => e.status === "geplant").length;
    const moeglich = events.filter((e) => e.status === "moeglich").length;
    return { total, fest, geplant, moeglich };
  }, [events]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-[var(--color-secondary)]">Lade Daten...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Header-Zeile */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jahresplan</h1>
          {activeSeason && (
            <p className="text-sm text-[var(--color-secondary)] mt-0.5">
              {activeSeason.name} · {formatDate(activeSeason.start_date)} – {formatDate(activeSeason.end_date)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* Spielzeit-Picker */}
          <select
            value={activeSeason?.id || ""}
            onChange={(e) => {
              const s = seasons.find((x) => x.id === Number(e.target.value));
              if (s) setActiveSeason(s);
            }}
            className="text-sm border border-[var(--color-border)] rounded-lg px-3 py-2 bg-white"
          >
            {seasons.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Quick-Stats */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        {[
          { label: "Gesamt", value: stats.total, color: "var(--color-primary)" },
          { label: "Fest", value: stats.fest, color: STATUS_COLORS.fest },
          { label: "Geplant", value: stats.geplant, color: STATUS_COLORS.geplant },
          { label: "Möglich", value: stats.moeglich, color: STATUS_COLORS.moeglich },
        ].map((s) => (
          <div key={s.label} className="card p-4 text-center">
            <div className="text-2xl font-semibold" style={{ color: s.color }}>{s.value}</div>
            <div className="text-xs text-[var(--color-secondary)] mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs text-[var(--color-secondary)] mr-1">Filter:</span>
        <select
          value={filterFormation}
          onChange={(e) => setFilterFormation(e.target.value)}
          className="text-xs border border-[var(--color-border)] rounded-md px-2 py-1 bg-white"
        >
          <option value="">Alle Formationen</option>
          {FORMATION_GROUPS.map((g) => (
            <option key={g.key} value={g.key}>{g.label}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="text-xs border border-[var(--color-border)] rounded-md px-2 py-1 bg-white"
        >
          <option value="">Alle Status</option>
          <option value="fest">Fest</option>
          <option value="geplant">Geplant</option>
          <option value="moeglich">Möglich</option>
        </select>
        <span className="text-xs text-[var(--color-secondary)] ml-2">
          {filteredEvents.length} Events
        </span>
      </div>

      {/* === TIMELINE === */}
      <div className="card overflow-hidden mb-6">
        <div className="overflow-x-auto">
          <div className="min-w-[1200px]">
            {/* Monats-Header */}
            <div className="flex border-b border-[var(--color-border)]">
              <div className="w-28 shrink-0 px-3 py-2 text-xs font-medium text-[var(--color-secondary)]">
                Formation
              </div>
              <div className="flex-1 flex">
                {weeks.map((w, i) => {
                  const month = w.getMonth();
                  const showMonth = i === 0 || weeks[i - 1]?.getMonth() !== month;
                  return (
                    <div
                      key={i}
                      className="flex-1 min-w-[24px] text-center text-[10px] text-[var(--color-secondary)] py-2 border-l border-[var(--color-border)]/30"
                      title={`KW ${getWeekNumber(w)}`}
                    >
                      {showMonth ? MONTH_NAMES[month] : ""}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Formation-Zeilen */}
            {FORMATION_GROUPS.map((group) => {
              const groupEvents = filteredEvents.filter(
                (e) => getFormationGroup(e.formation) === group.key
              );

              return (
                <div key={group.key} className="flex border-b border-[var(--color-border)]/50 hover:bg-black/[0.02]">
                  <div className="w-28 shrink-0 px-3 py-3 text-xs font-medium text-[var(--color-primary)] flex items-center">
                    <span
                      className="w-2 h-2 rounded-full mr-2 shrink-0"
                      style={{ backgroundColor: FORMATION_COLORS[group.key] || "#6E6E73" }}
                    />
                    {group.label}
                  </div>
                  <div className="flex-1 flex relative" style={{ minHeight: 40 }}>
                    {weeks.map((w, i) => {
                      const weekStr = w.toISOString().slice(0, 10);
                      const weekEnd = new Date(w);
                      weekEnd.setDate(weekEnd.getDate() + 6);
                      const weekEvents = groupEvents.filter((e) => {
                        const ed = new Date(e.event_date);
                        return ed >= w && ed <= weekEnd;
                      });

                      return (
                        <div
                          key={i}
                          className="flex-1 min-w-[24px] border-l border-[var(--color-border)]/20 flex flex-col items-center justify-center gap-0.5 py-1"
                        >
                          {weekEvents.map((ev) => (
                            <button
                              key={ev.id}
                              onClick={() => setSelectedEvent(ev)}
                              className="w-4 h-4 rounded-sm cursor-pointer transition-transform hover:scale-125"
                              style={{
                                backgroundColor: FORMATION_COLORS[ev.formation] || FORMATION_COLORS[group.key] || "#6E6E73",
                                opacity: ev.status === "moeglich" ? 0.4 : ev.status === "geplant" ? 0.7 : 1,
                              }}
                              title={`${formatDate(ev.event_date)} ${ev.dienst_type} — ${ev.programm || ev.ort || ""}`}
                            />
                          ))}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}

            {/* Auslastung (Dienste pro Woche) */}
            <div className="flex border-t-2 border-[var(--color-border)]">
              <div className="w-28 shrink-0 px-3 py-3 text-xs font-medium text-[var(--color-secondary)]">
                Dienste/Wo
              </div>
              <div className="flex-1 flex">
                {weeks.map((w, i) => {
                  const key = w.toISOString().slice(0, 10);
                  const count = weeklyLoad.get(key) || 0;
                  const max = 10;
                  const pct = Math.min(count / max * 100, 100);
                  const color = count >= 10 ? "var(--color-error)" : count >= 8 ? "var(--color-warning)" : "var(--color-success)";

                  return (
                    <div key={i} className="flex-1 min-w-[24px] border-l border-[var(--color-border)]/20 flex flex-col items-center justify-end py-1 px-0.5" style={{ height: 48 }}>
                      {count > 0 && (
                        <>
                          <div
                            className="w-full rounded-sm"
                            style={{ height: `${pct}%`, backgroundColor: color, minHeight: 4 }}
                          />
                          <span className="text-[9px] text-[var(--color-secondary)] mt-0.5">{count}</span>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Event-Detail Sidebar/Modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/20 flex items-center justify-center z-50" onClick={() => setSelectedEvent(null)}>
          <div className="card p-6 max-w-md w-full mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium">Event-Details</h3>
              <button onClick={() => setSelectedEvent(null)} className="text-[var(--color-secondary)] hover:text-[var(--color-primary)]">✕</button>
            </div>
            <div className="space-y-3">
              <div className="flex gap-2">
                <Badge label={selectedEvent.formation} variant="formation" value={selectedEvent.formation} />
                <Badge label={selectedEvent.status} variant="status" value={selectedEvent.status} />
                <Badge label={selectedEvent.dienst_type} />
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div><span className="text-[var(--color-secondary)]">Datum:</span> {formatDate(selectedEvent.event_date)}</div>
                <div><span className="text-[var(--color-secondary)]">Zeit:</span> {selectedEvent.start_time || "–"}{selectedEvent.end_time ? ` – ${selectedEvent.end_time}` : ""}</div>
                <div><span className="text-[var(--color-secondary)]">Ort:</span> {selectedEvent.ort || "–"}</div>
                <div><span className="text-[var(--color-secondary)]">Leitung:</span> {selectedEvent.leitung || "–"}</div>
              </div>
              {selectedEvent.programm && (
                <div className="text-sm"><span className="text-[var(--color-secondary)]">Programm:</span> {selectedEvent.programm}</div>
              )}
              {selectedEvent.kleidung && (
                <div className="text-sm"><span className="text-[var(--color-secondary)]">Kleidung:</span> {selectedEvent.kleidung}</div>
              )}
              {selectedEvent.project_name && (
                <div className="text-sm"><span className="text-[var(--color-secondary)]">Projekt:</span> {selectedEvent.project_name}</div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Info wenn keine Spielzeiten */}
      {seasons.length === 0 && (
        <div className="card p-12 text-center">
          <p className="text-[var(--color-secondary)] mb-4">Noch keine Spielzeit angelegt.</p>
          <a href="/events" className="btn-pill btn-primary">Spielzeit anlegen →</a>
        </div>
      )}
    </div>
  );
}
