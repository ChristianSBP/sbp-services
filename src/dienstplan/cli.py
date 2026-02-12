"""CLI für den Dienstplan-Generator der Sächsischen Bläserphilharmonie."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import click

from .config import load_config, is_htv_active
from .excel_parser.reader import read_jahresplan
from .excel_parser.event_extractor import extract_events
from .dienst_calculator import calculate_dienste
from .models.plan import Dienstplan
from .constraints.validator import TVKValidator
from .output.excel_writer import write_dienstplan
from .output.word_writer import write_dienstplan_docx


def _unique_path(path: Path) -> Path:
    """Erzeugt einen eindeutigen Dateinamen falls die Datei bereits existiert.

    Hängt '_2', '_3', ... an den Dateinamen an, bis ein freier Name gefunden wird.
    Beispiel: 'Dienstplan 2026.docx' → 'Dienstplan 2026_2.docx'
    """
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _write_output(plan: Dienstplan, output: str, config: dict, fmt: str):
    """Schreibt den Dienstplan im gewählten Format."""
    output_path = Path(output)

    if fmt == "docx":
        # Endung korrigieren falls nötig
        if output_path.suffix.lower() != ".docx":
            output_path = output_path.with_suffix(".docx")
    else:
        # Excel-Fallback
        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")

    # Eindeutigen Dateinamen erzeugen (kein Überschreiben)
    output_path = _unique_path(output_path)

    if fmt == "docx":
        write_dienstplan_docx(plan, output_path, config)
    else:
        write_dienstplan(plan, str(output_path))

    return str(output_path)


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), default=None,
              help="Pfad zur YAML-Konfiguration (überschreibt TVK-Defaults)")
@click.pass_context
def cli(ctx, config):
    """Dienstplan-Generator der Sächsischen Bläserphilharmonie.

    Generiert TVK/HTV-konforme Dienstpläne aus dem Jahresplan.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.argument("jahresplan", type=click.Path(exists=True))
@click.option("--start", "-s", type=click.DateTime(formats=["%Y-%m-%d"]),
              default="2026-03-01", help="Startdatum (YYYY-MM-DD)")
@click.option("--end", "-e", type=click.DateTime(formats=["%Y-%m-%d"]),
              default="2026-05-31", help="Enddatum (YYYY-MM-DD)")
@click.option("--output", "-o", type=click.Path(), default="dienstplan.docx",
              help="Ausgabedatei (.docx oder .xlsx)")
@click.option("--format", "-f", "fmt", type=click.Choice(["docx", "xlsx"]),
              default=None, help="Ausgabeformat (Default: aus Dateiendung oder docx)")
@click.option("--year", type=int, default=2026, help="Jahr des Jahresplans")
@click.pass_context
def generate(ctx, jahresplan, start, end, output, fmt, year):
    """Generiert einen neuen Dienstplan aus dem Jahresplan.

    Beispiel:
      dienstplan generate "Jahresplan 2026.xlsx" --start 2026-03-01 --end 2026-05-31
    """
    config = ctx.obj["config"]
    plan_start = start.date() if hasattr(start, 'date') else start
    plan_end = end.date() if hasattr(end, 'date') else end

    # Format aus --format oder Dateiendung ermitteln
    if fmt is None:
        fmt = "xlsx" if Path(output).suffix.lower() == ".xlsx" else "docx"

    htv_label = "HTV" if is_htv_active(config) else "TVK"
    click.echo(f"Modus: {htv_label}")

    click.echo(f"Lese Jahresplan: {jahresplan}")
    cells = read_jahresplan(jahresplan, year=year)
    click.echo(f"  {len(cells)} Einträge gefunden")

    click.echo("Extrahiere Events...")
    events = extract_events(cells, config)
    # Filtere auf Zeitraum
    events_in_range = [e for e in events if plan_start <= e.event_date <= plan_end]
    click.echo(f"  {len(events_in_range)} Events im Zeitraum {plan_start} – {plan_end}")

    click.echo("Berechne Dienste...")
    dienste = calculate_dienste(events_in_range, config, plan_start, plan_end)

    click.echo("Erstelle Dienstplan...")
    plan = Dienstplan.from_events(events_in_range, dienste, plan_start, plan_end)

    click.echo(f"Prüfe {htv_label}-Konformität...")
    validator = TVKValidator(config)
    violations = validator.validate(plan)
    summary = validator.summary(violations)
    click.echo(f"  {summary['errors']} Fehler, {summary['warnings']} Warnungen, {summary['infos']} Hinweise")

    click.echo(f"Schreibe Dienstplan ({fmt.upper()}): {output}")
    final_path = _write_output(plan, output, config, fmt)

    click.echo(f"\n✓ Fertig! Dienstplan gespeichert: {final_path}")
    if summary['errors'] > 0:
        click.echo(click.style(
            f"\n  ACHTUNG: {summary['errors']} {htv_label}-Verstöße gefunden!",
            fg="red", bold=True
        ))


@cli.command()
@click.argument("dienstplan_pdf", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default="validierung.docx",
              help="Ausgabedatei (.docx oder .xlsx)")
@click.option("--format", "-f", "fmt", type=click.Choice(["docx", "xlsx"]),
              default=None, help="Ausgabeformat (Default: aus Dateiendung oder docx)")
@click.pass_context
def validate(ctx, dienstplan_pdf, output, fmt):
    """Validiert einen bestehenden Dienstplan (PDF) gegen TVK/HTV-Regeln.

    Beispiel:
      dienstplan validate "Dienstplan 06.02.-03.05.2026.pdf"
    """
    config = ctx.obj["config"]

    if fmt is None:
        fmt = "xlsx" if Path(output).suffix.lower() == ".xlsx" else "docx"

    click.echo(f"Lese bestehenden Dienstplan: {dienstplan_pdf}")

    from .pdf_parser.dienstplan_reader import read_existing_dienstplan
    events, dienste, plan_start, plan_end = read_existing_dienstplan(dienstplan_pdf)
    click.echo(f"  {len(dienste)} Tage importiert ({plan_start} – {plan_end})")

    plan = Dienstplan.from_events(events, dienste, plan_start, plan_end)

    htv_label = "HTV" if is_htv_active(config) else "TVK"
    click.echo(f"Prüfe {htv_label}-Konformität...")
    validator = TVKValidator(config)
    violations = validator.validate(plan)
    summary = validator.summary(violations)

    click.echo(f"  {summary['errors']} Fehler, {summary['warnings']} Warnungen, {summary['infos']} Hinweise")

    click.echo(f"Schreibe Validierungsbericht ({fmt.upper()}): {output}")
    final_path = _write_output(plan, output, config, fmt)
    click.echo(f"✓ Fertig! Bericht gespeichert: {final_path}")


@cli.command()
@click.argument("dienstplan_pdf", type=click.Path(exists=True))
@click.argument("jahresplan", type=click.Path(exists=True))
@click.option("--until", "until_date", type=click.DateTime(formats=["%Y-%m-%d"]),
              default="2026-05-31", help="Bis-Datum für Erweiterung")
@click.option("--output", "-o", type=click.Path(), default="erweitert.docx",
              help="Ausgabedatei (.docx oder .xlsx)")
@click.option("--format", "-f", "fmt", type=click.Choice(["docx", "xlsx"]),
              default=None, help="Ausgabeformat (Default: aus Dateiendung oder docx)")
@click.option("--year", type=int, default=2026)
@click.pass_context
def extend(ctx, dienstplan_pdf, jahresplan, until_date, output, fmt, year):
    """Erweitert einen bestehenden Dienstplan mit Daten aus dem Jahresplan.

    Beispiel:
      dienstplan extend "Dienstplan.pdf" "Jahresplan 2026.xlsx" --until 2026-05-31
    """
    config = ctx.obj["config"]
    plan_end = until_date.date() if hasattr(until_date, 'date') else until_date

    if fmt is None:
        fmt = "xlsx" if Path(output).suffix.lower() == ".xlsx" else "docx"

    click.echo(f"Lese bestehenden Dienstplan: {dienstplan_pdf}")
    from .pdf_parser.dienstplan_reader import read_existing_dienstplan
    existing_events, existing_dienste, existing_start, existing_end = read_existing_dienstplan(dienstplan_pdf)
    click.echo(f"  Bestehend: {existing_start} – {existing_end}")

    click.echo(f"Lese Jahresplan: {jahresplan}")
    cells = read_jahresplan(jahresplan, year=year)
    new_events = extract_events(cells, config)
    # Nur Events NACH dem bestehenden Dienstplan
    extension_start = existing_end + timedelta(days=1)
    new_events_in_range = [e for e in new_events if extension_start <= e.event_date <= plan_end]
    click.echo(f"  {len(new_events_in_range)} neue Events ({extension_start} – {plan_end})")

    new_dienste = calculate_dienste(new_events_in_range, config, extension_start, plan_end)

    # Kombiniere bestehende + neue Dienste
    all_dienste = existing_dienste + new_dienste
    all_events = existing_events + new_events_in_range

    plan = Dienstplan.from_events(all_events, all_dienste, existing_start, plan_end)

    htv_label = "HTV" if is_htv_active(config) else "TVK"
    validator = TVKValidator(config)
    violations = validator.validate(plan)
    summary = validator.summary(violations)
    click.echo(f"  {summary['errors']} Fehler, {summary['warnings']} Warnungen")

    final_path = _write_output(plan, output, config, fmt)
    click.echo(f"✓ Fertig! Erweiterter Dienstplan: {final_path}")


@cli.command()
@click.argument("jahresplan", type=click.Path(exists=True))
@click.option("--start", "-s", type=click.DateTime(formats=["%Y-%m-%d"]),
              default="2026-03-01", help="Startdatum (YYYY-MM-DD)")
@click.option("--end", "-e", type=click.DateTime(formats=["%Y-%m-%d"]),
              default="2026-05-31", help="Enddatum (YYYY-MM-DD)")
@click.option("--output-dir", "-o", type=click.Path(), default=None,
              help="Ausgabeverzeichnis (Default: ~/Downloads/Dienstplan Einzelpläne MM-MM)")
@click.option("--year", type=int, default=2026, help="Jahr des Jahresplans")
@click.option("--musician", "-m", type=str, default=None,
              help="Nur für einen Musiker (Nachname)")
@click.pass_context
def einzelplaene(ctx, jahresplan, start, end, output_dir, year, musician):
    """Generiert individuelle Dienstpläne für alle Musiker.

    Beispiel:
      dienstplan einzelplaene "Jahresplan 2026.xlsx"
      dienstplan einzelplaene "Jahresplan 2026.xlsx" -m Scheibe
    """
    from .roster import load_roster
    from .individual_plan import create_individual_plan
    from .output.individual_writer import write_individual_docx

    config = ctx.obj["config"]
    plan_start = start.date() if hasattr(start, 'date') else start
    plan_end = end.date() if hasattr(end, 'date') else end

    # Ausgabeverzeichnis bestimmen
    if output_dir is None:
        month_range = f"{plan_start.strftime('%m')}-{plan_end.strftime('%m')}"
        output_dir = f"~/Downloads/Dienstplan Einzelpläne {month_range}"
    output_path = Path(output_dir).expanduser()
    output_path.mkdir(parents=True, exist_ok=True)

    htv_label = "HTV" if is_htv_active(config) else "TVK"
    click.echo(f"Modus: {htv_label}")

    # Kollektiven Plan generieren
    click.echo(f"Lese Jahresplan: {jahresplan}")
    cells = read_jahresplan(jahresplan, year=year)
    click.echo(f"  {len(cells)} Einträge gefunden")

    click.echo("Extrahiere Events...")
    events = extract_events(cells, config)
    events_in_range = [e for e in events if plan_start <= e.event_date <= plan_end]
    click.echo(f"  {len(events_in_range)} Events im Zeitraum")

    click.echo("Berechne Dienste...")
    dienste = calculate_dienste(events_in_range, config, plan_start, plan_end)
    plan = Dienstplan.from_events(events_in_range, dienste, plan_start, plan_end)

    # Roster laden
    roster = load_roster()
    all_musicians = roster.all_musicians  # Inkl. vakante Stellen

    if musician:
        all_musicians = [m for m in all_musicians
                         if musician.lower() in m.nachname.lower()
                         or musician.lower() in m.name.lower()]
        if not all_musicians:
            click.echo(f"Kein Musiker mit '{musician}' gefunden.")
            return

    click.echo(f"\nGeneriere {len(all_musicians)} individuelle Dienstpläne...")

    for m in all_musicians:
        individual = create_individual_plan(plan, m, config)
        filename = m.filename
        filepath = _unique_path(output_path / filename)

        write_individual_docx(individual, m, filepath, config)
        ens = f" [{', '.join(sorted(m.ensembles))}]" if m.ensembles else ""
        click.echo(f"  {m.display_name:35s} → {filepath.name}{ens}")

    click.echo(f"\n✓ Fertig! {len(all_musicians)} Einzelpläne in: {output_path}")


if __name__ == "__main__":
    cli()
