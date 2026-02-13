/* Dashboard — Jahreskalender mit 12-Monats-Grid und Detail-Panel */

import { useState, useEffect, useMemo, useCallback } from "react";
import { seasonsAPI, eventsAPI } from "../api/client";
import Badge from "../components/common/Badge";
import type { Season, SBPEvent, EventStatus } from "../types";
import { FORMATION_COLORS, DIENST_TYPE_COLORS } from "../types";

/* ──── Hilfsfunktionen ──── */

const MONTH_NAMES = [
  "Januar", "Februar", "März", "April", "Mai", "Juni",
  "Juli", "August", "September", "Oktober", "November", "Dezember",
];

const WDAY_LABELS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

function daysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

/** Wochentag 0=Mo, 6=So */
function weekdayMondayBased(year: number, month: number, day: number): number {
  const d = new Date(year, month, day).getDay();
  return d === 0 ? 6 : d - 1;
}

function dateKey(d: string): string {
  return d.slice(0, 10);
}

function formatDateLong(s: string): string {
  const d = new Date(s + "T12:00:00");
  return d.toLocaleDateString("de-DE", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formatTime(t: string | null): string {
  if (!t) return "";
  return t.slice(0, 5);
}

function isToday(year: number, month: number, day: number): boolean {
  const now = new Date();
  return now.getFullYear() === year && now.getMonth() === month && now.getDate() === day;
}

function isSunday(year: number, month: number, day: number): boolean {
  return new Date(year, month, day).getDay() === 0;
}

function isSaturday(year: number, month: number, day: number): boolean {
  return new Date(year, month, day).getDay() === 6;
}

/** Dot-Farbe: primaer nach Dienst-Typ, Fallback Formation */
function getDotColor(ev: SBPEvent): string {
  return DIENST_TYPE_COLORS[ev.dienst_type] || FORMATION_COLORS[ev.formation] || "#6E6E73";
}

/** Dienst-Typ Kurzname fuer Legende */
const DIENST_GROUPS = [
  { label: "Konzerte", types: ["Konzert", "Abo-Konzert", "SK", "Babykonzert", "Gastspiel"], color: "#0071E3" },
  { label: "Proben", types: ["Probe", "GP", "HP", "Anspielprobe"], color: "#34C759" },
  { label: "Besonderes", types: ["Dirigierkurs", "Podcast", "Tonaufnahme", "Akademiedienst"], color: "#FF9F0A" },
  { label: "Frei/Urlaub", types: ["Urlaub", "Frei", "RZA", "Reise"], color: "#AEAEB2" },
  { label: "Sonstiges", types: ["Dienstberatung", "Probespiel", "Sonstiges"], color: "#6E6E73" },
];

/* ──── Formations-Gruppen ──── */
const FORMATION_GROUPS = [
  { key: "SBP", label: "SBP" },
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

/* ──── Hauptkomponente ──── */

export default function Dashboard() {
  const [seasons, setSeasons] = useState<Season[]>([]);
  const [allEvents, setAllEvents] = useState<SBPEvent[]>([]);
  const [selectedYear, setSelectedYear] = useState<number>(new Date().getFullYear());
  const [loading, setLoading] = useState(true);
  const [filterFormation, setFilterFormation] = useState<string>("");
  const [filterStatus, setFilterStatus] = useState<string>("");
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // Verfuegbare Jahre aus den Seasons ableiten
  const availableYears = useMemo(() => {
    const years = new Set<number>();
    for (const s of seasons) {
      const startYear = new Date(s.start_date).getFullYear();
      const endYear = new Date(s.end_date).getFullYear();
      for (let y = startYear; y <= endYear; y++) years.add(y);
    }
    return Array.from(years).sort();
  }, [seasons]);

  // Seasons + Events laden
  useEffect(() => {
    setLoading(true);
    seasonsAPI.list().then((res) => {
      const s = res.data as Season[];
      setSeasons(s);
      // Aktuelle Spielzeit bestimmt initiales Jahr
      const active = s.find((x) => x.is_active);
      if (active) {
        setSelectedYear(new Date(active.start_date).getFullYear());
      }
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  // Alle Events fuer das gewaehlte Jahr laden (aus allen relevanten Seasons)
  useEffect(() => {
    if (seasons.length === 0) return;
    // Seasons finden die in das Jahr fallen
    const relevantSeasons = seasons.filter((s) => {
      const startYear = new Date(s.start_date).getFullYear();
      const endYear = new Date(s.end_date).getFullYear();
      return startYear <= selectedYear && endYear >= selectedYear;
    });

    if (relevantSeasons.length === 0) {
      setAllEvents([]);
      return;
    }

    // Events aus allen relevanten Seasons laden
    Promise.all(
      relevantSeasons.map((s) => eventsAPI.list({ season_id: s.id }))
    ).then((results) => {
      const all = results.flatMap((r) => r.data as SBPEvent[]);
      // Nur Events im gewaehlten Jahr
      const yearEvents = all.filter(
        (e) => new Date(e.event_date).getFullYear() === selectedYear
      );
      // Duplikate entfernen (falls ein Event in mehreren Seasons liegt)
      const seen = new Set<number>();
      const unique = yearEvents.filter((e) => {
        if (seen.has(e.id)) return false;
        seen.add(e.id);
        return true;
      });
      setAllEvents(unique);
    }).catch(() => setAllEvents([]));
  }, [seasons, selectedYear]);

  // Gefilterte Events
  const filteredEvents = useMemo(() => {
    let result = allEvents;
    if (filterFormation) result = result.filter((e) => getFormationGroup(e.formation) === filterFormation);
    if (filterStatus) result = result.filter((e) => e.status === filterStatus);
    return result;
  }, [allEvents, filterFormation, filterStatus]);

  // Events nach Datum gruppieren
  const eventsByDate = useMemo(() => {
    const map = new Map<string, SBPEvent[]>();
    for (const e of filteredEvents) {
      const key = dateKey(e.event_date);
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(e);
    }
    return map;
  }, [filteredEvents]);

  // Quick-Stats
  const stats = useMemo(() => {
    const total = filteredEvents.length;
    const konzerte = filteredEvents.filter((e) =>
      ["Konzert", "Abo-Konzert", "SK", "Babykonzert", "Gastspiel"].includes(e.dienst_type)
    ).length;
    const proben = filteredEvents.filter((e) =>
      ["Probe", "GP", "HP", "Anspielprobe"].includes(e.dienst_type)
    ).length;
    const urlaub = filteredEvents.filter((e) =>
      ["Urlaub", "Frei", "RZA"].includes(e.dienst_type)
    ).length;
    const fest = filteredEvents.filter((e) => e.status === "fest").length;
    return { total, konzerte, proben, urlaub, fest };
  }, [filteredEvents]);

  // Events fuer den selektierten Tag
  const selectedDayEvents = useMemo(() => {
    if (!selectedDate) return [];
    return eventsByDate.get(selectedDate) || [];
  }, [selectedDate, eventsByDate]);

  const handleDayClick = useCallback((year: number, month: number, day: number) => {
    const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    setSelectedDate((prev) => (prev === key ? null : key));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-[var(--color-secondary)]">Lade Daten...</div>
      </div>
    );
  }

  return (
    <div className="max-w-[1440px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* ──── Header ──── */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Jahresplan {selectedYear}</h1>
          <p className="text-sm text-[var(--color-secondary)] mt-0.5">
            {filteredEvents.length} Events · {stats.konzerte} Konzerte · {stats.proben} Proben
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Jahr-Picker */}
          <button
            onClick={() => setSelectedYear((y) => y - 1)}
            disabled={!availableYears.includes(selectedYear - 1)}
            className="w-8 h-8 flex items-center justify-center rounded-full border border-[var(--color-border)] text-sm hover:bg-black/5 disabled:opacity-30"
          >
            ‹
          </button>
          <select
            value={selectedYear}
            onChange={(e) => setSelectedYear(Number(e.target.value))}
            className="text-sm font-medium border border-[var(--color-border)] rounded-lg px-3 py-1.5 bg-white"
          >
            {availableYears.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
          <button
            onClick={() => setSelectedYear((y) => y + 1)}
            disabled={!availableYears.includes(selectedYear + 1)}
            className="w-8 h-8 flex items-center justify-center rounded-full border border-[var(--color-border)] text-sm hover:bg-black/5 disabled:opacity-30"
          >
            ›
          </button>
        </div>
      </div>

      {/* ──── Quick-Stats ──── */}
      <div className="grid grid-cols-5 gap-3 mb-5">
        {[
          { label: "Gesamt", value: stats.total, color: "var(--color-primary)" },
          { label: "Konzerte", value: stats.konzerte, color: "#0071E3" },
          { label: "Proben", value: stats.proben, color: "#34C759" },
          { label: "Frei/Urlaub", value: stats.urlaub, color: "#AEAEB2" },
          { label: "Fest", value: stats.fest, color: "var(--color-primary)" },
        ].map((s) => (
          <div key={s.label} className="card p-3 text-center">
            <div className="text-xl font-semibold" style={{ color: s.color }}>{s.value}</div>
            <div className="text-[10px] text-[var(--color-secondary)] mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* ──── Filter + Legende ──── */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--color-secondary)]">Filter:</span>
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
        </div>
        {/* Mini-Legende */}
        <div className="flex items-center gap-3 flex-wrap">
          {DIENST_GROUPS.map((g) => (
            <div key={g.label} className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: g.color }} />
              <span className="text-[10px] text-[var(--color-secondary)]">{g.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ──── Kalender + Detail-Panel ──── */}
      <div className="flex gap-5">
        {/* Kalender-Grid: 12 Monate */}
        <div className="flex-1 grid grid-cols-3 xl:grid-cols-4 gap-3">
          {Array.from({ length: 12 }, (_, month) => (
            <MonthGrid
              key={month}
              year={selectedYear}
              month={month}
              eventsByDate={eventsByDate}
              selectedDate={selectedDate}
              onDayClick={handleDayClick}
            />
          ))}
        </div>

        {/* Detail-Panel (rechts) */}
        <div className="w-80 shrink-0 hidden lg:block">
          <div className="card p-4 sticky top-20">
            {selectedDate ? (
              <>
                <h3 className="text-sm font-semibold mb-3">
                  {formatDateLong(selectedDate)}
                </h3>
                {selectedDayEvents.length === 0 ? (
                  <p className="text-xs text-[var(--color-secondary)] py-4 text-center">
                    Keine Events an diesem Tag.
                  </p>
                ) : (
                  <div className="space-y-2 max-h-[calc(100vh-200px)] overflow-y-auto">
                    {selectedDayEvents
                      .sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""))
                      .map((ev) => (
                        <EventCard key={ev.id} event={ev} />
                      ))}
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8">
                <div className="text-3xl mb-2">📅</div>
                <p className="text-xs text-[var(--color-secondary)]">
                  Klicken Sie auf einen Tag,<br />um die Events zu sehen.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Mobile: Detail-Modal statt Panel */}
      {selectedDate && selectedDayEvents.length > 0 && (
        <div className="lg:hidden fixed inset-0 bg-black/20 flex items-end z-50" onClick={() => setSelectedDate(null)}>
          <div
            className="bg-white rounded-t-2xl w-full max-h-[70vh] overflow-y-auto p-5"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold">{formatDateLong(selectedDate)}</h3>
              <button onClick={() => setSelectedDate(null)} className="text-[var(--color-secondary)]">✕</button>
            </div>
            <div className="space-y-2">
              {selectedDayEvents
                .sort((a, b) => (a.start_time || "").localeCompare(b.start_time || ""))
                .map((ev) => (
                  <EventCard key={ev.id} event={ev} />
                ))}
            </div>
          </div>
        </div>
      )}

      {/* ──── Keine Daten ──── */}
      {seasons.length === 0 && (
        <div className="card p-12 text-center mt-8">
          <p className="text-[var(--color-secondary)] mb-4">Noch keine Spielzeit angelegt.</p>
          <a href="/events" className="btn-pill btn-primary">Spielzeit anlegen →</a>
        </div>
      )}
    </div>
  );
}


/* ──── Monats-Grid Komponente ──── */

function MonthGrid({
  year,
  month,
  eventsByDate,
  selectedDate,
  onDayClick,
}: {
  year: number;
  month: number;
  eventsByDate: Map<string, SBPEvent[]>;
  selectedDate: string | null;
  onDayClick: (year: number, month: number, day: number) => void;
}) {
  const days = daysInMonth(year, month);
  const firstDayOffset = weekdayMondayBased(year, month, 1);
  const now = new Date();
  const isCurrentMonth = now.getFullYear() === year && now.getMonth() === month;

  return (
    <div className="card p-3">
      {/* Monatsname */}
      <h4 className={`text-xs font-semibold mb-2 ${
        isCurrentMonth ? "text-[var(--color-accent)]" : "text-[var(--color-primary)]"
      }`}>
        {MONTH_NAMES[month]}
      </h4>

      {/* Wochentags-Header */}
      <div className="grid grid-cols-7 mb-1">
        {WDAY_LABELS.map((d) => (
          <div key={d} className="text-center text-[9px] text-[var(--color-secondary)] font-medium">
            {d}
          </div>
        ))}
      </div>

      {/* Tages-Grid */}
      <div className="grid grid-cols-7 gap-px">
        {/* Leere Zellen vor dem 1. */}
        {Array.from({ length: firstDayOffset }, (_, i) => (
          <div key={`empty-${i}`} className="aspect-square" />
        ))}

        {/* Tages-Zellen */}
        {Array.from({ length: days }, (_, i) => {
          const day = i + 1;
          const key = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
          const dayEvents = eventsByDate.get(key) || [];
          const isSelected = selectedDate === key;
          const today = isToday(year, month, day);
          const sunday = isSunday(year, month, day);
          const saturday = isSaturday(year, month, day);

          return (
            <button
              key={day}
              onClick={() => onDayClick(year, month, day)}
              className={`
                aspect-square rounded-md flex flex-col items-center justify-start pt-0.5 relative
                transition-all duration-100
                ${isSelected
                  ? "bg-[var(--color-accent)] text-white ring-2 ring-[var(--color-accent)] ring-offset-1"
                  : today
                    ? "bg-[var(--color-accent)]/10 ring-1 ring-[var(--color-accent)]/30"
                    : dayEvents.length > 0
                      ? "bg-black/[0.03] hover:bg-black/[0.07]"
                      : sunday || saturday
                        ? "bg-black/[0.02] hover:bg-black/[0.05]"
                        : "hover:bg-black/[0.04]"
                }
                ${sunday && !isSelected ? "text-[var(--color-error)]/60" : ""}
              `}
              title={
                dayEvents.length > 0
                  ? dayEvents.map((e) => `${e.dienst_type}: ${e.programm || e.ort || ""}`).join("\n")
                  : ""
              }
            >
              {/* Tagesnummer */}
              <span className={`text-[9px] leading-none font-medium ${
                isSelected ? "text-white" : today ? "text-[var(--color-accent)] font-bold" : ""
              }`}>
                {day}
              </span>

              {/* Event-Dots */}
              {dayEvents.length > 0 && (
                <div className="flex flex-wrap items-center justify-center gap-[2px] mt-0.5 px-0.5">
                  {dayEvents.slice(0, 4).map((ev, idx) => (
                    <span
                      key={idx}
                      className="w-[5px] h-[5px] rounded-full"
                      style={{
                        backgroundColor: isSelected ? "white" : getDotColor(ev),
                        opacity: isSelected ? 0.9 : ev.status === "moeglich" ? 0.4 : ev.status === "geplant" ? 0.7 : 1,
                      }}
                    />
                  ))}
                  {dayEvents.length > 4 && (
                    <span className={`text-[7px] font-bold ${isSelected ? "text-white/80" : "text-[var(--color-secondary)]"}`}>
                      +{dayEvents.length - 4}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}


/* ──── Event-Card fuer Detail-Panel ──── */

function EventCard({ event: ev }: { event: SBPEvent }) {
  return (
    <div
      className="p-2.5 rounded-lg border border-[var(--color-border)]/50 hover:border-[var(--color-border)] transition-colors"
      style={{ borderLeft: `3px solid ${getDotColor(ev)}` }}
    >
      {/* Kopfzeile: Typ + Formation + Status */}
      <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
        <Badge label={ev.dienst_type} />
        <Badge label={ev.formation} variant="formation" value={ev.formation} />
        <Badge label={ev.status} variant="status" value={ev.status as EventStatus} />
      </div>

      {/* Details */}
      <div className="space-y-0.5 text-xs">
        {/* Zeit */}
        {ev.start_time && (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--color-secondary)] w-12">Zeit</span>
            <span className="font-medium">
              {formatTime(ev.start_time)}
              {ev.end_time ? ` – ${formatTime(ev.end_time)}` : ""}
            </span>
          </div>
        )}

        {/* Programm */}
        {ev.programm && (
          <div className="flex items-start gap-1.5">
            <span className="text-[var(--color-secondary)] w-12 shrink-0">Progr.</span>
            <span className="font-medium">{ev.programm}</span>
          </div>
        )}

        {/* Ort */}
        {ev.ort && (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--color-secondary)] w-12">Ort</span>
            <span>{ev.ort}</span>
          </div>
        )}

        {/* Leitung */}
        {ev.leitung && (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--color-secondary)] w-12">Leitung</span>
            <span>{ev.leitung}</span>
          </div>
        )}

        {/* Kleidung */}
        {ev.kleidung && (
          <div className="flex items-center gap-1.5">
            <span className="text-[var(--color-secondary)] w-12">Kleidg.</span>
            <span>{ev.kleidung}</span>
          </div>
        )}
      </div>
    </div>
  );
}
