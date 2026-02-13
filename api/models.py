"""SQLAlchemy-Modelle fuer Planung SBP.

Zentrale Datenbank-Modelle fuer Spielzeiten, Projekte, Events,
Musiker und generierte Dienstplaene.
"""

from datetime import datetime, date, time

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


# ---------------------------------------------------------------------------
# Benutzer
# ---------------------------------------------------------------------------

class User(db.Model):
    """Benutzer (Admin oder Musiker-Zugang)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="musiker")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.email or self.role}>"


# ---------------------------------------------------------------------------
# Spielzeiten
# ---------------------------------------------------------------------------

class Season(db.Model):
    """Spielzeit (Rumpf 2026: Aug-Dez, ab 2027: Kalenderjahr Jan-Dez)."""

    __tablename__ = "seasons"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # z.B. "2026 (Rumpf)", "2027"
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_active = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Beziehungen
    projects = db.relationship("Project", backref="season", lazy=True,
                               cascade="all, delete-orphan")
    events = db.relationship("Event", backref="season", lazy=True,
                             cascade="all, delete-orphan")
    generated_plans = db.relationship("GeneratedPlan", backref="season", lazy=True,
                                      cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Season {self.name}>"


# ---------------------------------------------------------------------------
# Projekte
# ---------------------------------------------------------------------------

class Project(db.Model):
    """Projekt buendelt zusammengehoerige Events (z.B. 'NY-Tournee April 2026')."""

    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="geplant")  # fest/geplant/moeglich
    formation = db.Column(db.String(50), nullable=True)
    conductor = db.Column(db.String(120), nullable=True)
    soloist = db.Column(db.String(200), nullable=True)
    moderator = db.Column(db.String(120), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Beziehungen
    events = db.relationship("Event", backref="project", lazy=True)

    def __repr__(self):
        return f"<Project {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "season_id": self.season_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "formation": self.formation,
            "conductor": self.conductor,
            "soloist": self.soloist,
            "moderator": self.moderator,
            "notes": self.notes,
            "event_count": len(self.events) if self.events else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class Event(db.Model):
    """Einzelnes Event/Dienst im Jahresplan."""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=False)

    # Zeitdaten
    event_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=True)
    end_time = db.Column(db.Time, nullable=True)

    # Klassifikation
    dienst_type = db.Column(db.String(50), nullable=False, default="Sonstiges")
    formation = db.Column(db.String(50), nullable=False, default="Unbekannt")
    status = db.Column(db.String(20), nullable=False, default="geplant")  # fest/geplant/moeglich

    # Inhalt
    programm = db.Column(db.Text, nullable=True, default="")
    ort = db.Column(db.String(200), nullable=True, default="")
    ort_adresse = db.Column(db.String(300), nullable=True, default="")
    leitung = db.Column(db.String(120), nullable=True, default="")
    kleidung = db.Column(db.String(100), nullable=True, default="")
    sonstiges = db.Column(db.Text, nullable=True, default="")

    # Migration
    raw_text = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Event {self.event_date} {self.dienst_type}>"

    def to_dict(self):
        return {
            "id": self.id,
            "project_id": self.project_id,
            "season_id": self.season_id,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "start_time": self.start_time.strftime("%H:%M") if self.start_time else None,
            "end_time": self.end_time.strftime("%H:%M") if self.end_time else None,
            "dienst_type": self.dienst_type,
            "formation": self.formation,
            "status": self.status,
            "programm": self.programm or "",
            "ort": self.ort or "",
            "ort_adresse": self.ort_adresse or "",
            "leitung": self.leitung or "",
            "kleidung": self.kleidung or "",
            "sonstiges": self.sonstiges or "",
            "raw_text": self.raw_text or "",
            "project_name": self.project.name if self.project else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# Musiker
# ---------------------------------------------------------------------------

class Musician(db.Model):
    """Musiker der SBP (ersetzt roster.yaml)."""

    __tablename__ = "musicians"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(120), nullable=False)
    register = db.Column(db.String(80), nullable=False)
    gruppe = db.Column(db.String(20), nullable=False)  # HOLZ / BLECH
    anteil = db.Column(db.Integer, default=100)
    zusatz = db.Column(db.String(120), nullable=True, default="")
    is_vakant = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Beziehungen
    ensembles = db.relationship("MusicianEnsemble", backref="musician", lazy=True,
                                cascade="all, delete-orphan")
    individual_plans = db.relationship("IndividualPlan", backref="musician", lazy=True)

    @property
    def display_name(self):
        if self.is_vakant:
            return f"vakant ({self.position})"
        return self.name

    @property
    def nachname(self):
        parts = self.name.split()
        return parts[-1] if parts else self.name

    @property
    def vorname(self):
        parts = self.name.split()
        return parts[0] if len(parts) > 1 else ""

    @property
    def sort_key(self):
        if self.is_vakant:
            return f"zzz_{self.position}"
        return f"{self.nachname}_{self.vorname}"

    @property
    def ensemble_set(self):
        """Ensemble-Namen als Set (fuer Kompatibilitaet mit roster.Musician)."""
        return {e.ensemble for e in self.ensembles}

    def __repr__(self):
        return f"<Musician {self.display_name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "position": self.position,
            "register": self.register,
            "gruppe": self.gruppe,
            "anteil": self.anteil,
            "zusatz": self.zusatz or "",
            "is_vakant": self.is_vakant,
            "display_name": self.display_name,
            "ensembles": [e.ensemble for e in self.ensembles],
        }


class MusicianEnsemble(db.Model):
    """Ensemble-Zugehoerigkeit eines Musikers."""

    __tablename__ = "musician_ensembles"

    id = db.Column(db.Integer, primary_key=True)
    musician_id = db.Column(db.Integer, db.ForeignKey("musicians.id"), nullable=False)
    ensemble = db.Column(db.String(50), nullable=False)

    def __repr__(self):
        return f"<MusicianEnsemble {self.musician_id} -> {self.ensemble}>"


# ---------------------------------------------------------------------------
# Generierte Dienstplaene
# ---------------------------------------------------------------------------

class GeneratedPlan(db.Model):
    """Ein generierter Dienstplan-Durchlauf."""

    __tablename__ = "generated_plans"

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey("seasons.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    plan_start = db.Column(db.Date, nullable=False)
    plan_end = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="generating")
    violations_json = db.Column(db.Text, nullable=True)

    # Kollektiver Plan als BLOB
    collective_docx = db.Column(db.LargeBinary, nullable=True)
    collective_pdf = db.Column(db.LargeBinary, nullable=True)

    # Beziehung zu Einzelplaenen
    individual_plans = db.relationship(
        "IndividualPlan", backref="generated_plan", lazy=True,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<GeneratedPlan {self.plan_start} - {self.plan_end}>"

    def to_dict(self):
        return {
            "id": self.id,
            "season_id": self.season_id,
            "plan_start": self.plan_start.isoformat() if self.plan_start else None,
            "plan_end": self.plan_end.isoformat() if self.plan_end else None,
            "status": self.status,
            "has_collective_docx": self.collective_docx is not None,
            "has_collective_pdf": self.collective_pdf is not None,
            "individual_count": len(self.individual_plans) if self.individual_plans else 0,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IndividualPlan(db.Model):
    """Individueller Dienstplan eines Musikers."""

    __tablename__ = "individual_plans"

    id = db.Column(db.Integer, primary_key=True)
    generated_plan_id = db.Column(
        db.Integer, db.ForeignKey("generated_plans.id"), nullable=False
    )
    musician_id = db.Column(
        db.Integer, db.ForeignKey("musicians.id"), nullable=True
    )
    display_name = db.Column(db.String(200), nullable=False)
    is_vakant = db.Column(db.Boolean, default=False)

    # DOCX + PDF als BLOB
    docx_data = db.Column(db.LargeBinary, nullable=True)
    pdf_data = db.Column(db.LargeBinary, nullable=True)

    @property
    def sort_key(self):
        if self.is_vakant:
            return f"zzz_{self.display_name}"
        parts = self.display_name.split()
        nachname = parts[-1] if parts else self.display_name
        vorname = parts[0] if len(parts) > 1 else ""
        return f"{nachname}_{vorname}"

    def __repr__(self):
        return f"<IndividualPlan {self.display_name}>"


# ---------------------------------------------------------------------------
# Zukunfts-Tabellen (Schema vorbereitet, UI spaeter)
# ---------------------------------------------------------------------------

class Checklist(db.Model):
    """Laufzettel / Checkliste pro Projekt."""

    __tablename__ = "checklists"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    checklist_type = db.Column(db.String(50), nullable=False, default="general")
    data_json = db.Column(db.Text, nullable=True)  # Flexibles JSON fuer Checklisten-Daten
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    project = db.relationship("Project", backref="checklists")


class ProgramPiece(db.Model):
    """Programm-Stueck (Laufzettel Sheet 2: Programm Detail)."""

    __tablename__ = "program_pieces"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    archive_nr = db.Column(db.String(50), nullable=True)
    title = db.Column(db.String(300), nullable=False)
    composer = db.Column(db.String(200), nullable=True)
    arranger = db.Column(db.String(200), nullable=True)
    material_source = db.Column(db.String(20), nullable=True)  # A=Archiv, K=Kauf, L=Leihe
    publisher = db.Column(db.String(200), nullable=True)
    rights = db.Column(db.String(200), nullable=True)
    instrumentation = db.Column(db.Text, nullable=True)
    soloist = db.Column(db.String(200), nullable=True)
    orchestral_solos = db.Column(db.Text, nullable=True)
    special_instruments = db.Column(db.Text, nullable=True)

    project = db.relationship("Project", backref="program_pieces")


class SubstituteMusician(db.Model):
    """Aushilfen-Tracking (Laufzettel Sheet 3)."""

    __tablename__ = "substitute_musicians"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    instrument = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(200), nullable=True)
    music_sent = db.Column(db.Boolean, default=False)
    done = db.Column(db.Boolean, default=False)

    project = db.relationship("Project", backref="substitute_musicians")
