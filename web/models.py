"""SQLAlchemy-Modelle fuer die SBP Web-App."""

from datetime import datetime, date

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """Benutzer (Admin oder Musiker-Zugang)."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="musiker")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<User {self.email or self.role}>"


class GeneratedPlan(db.Model):
    """Ein generierter Dienstplan-Durchlauf."""

    __tablename__ = "generated_plans"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    plan_start = db.Column(db.Date, nullable=False)
    plan_end = db.Column(db.Date, nullable=False)
    jahresplan_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="generating")

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


class IndividualPlan(db.Model):
    """Individueller Dienstplan eines Musikers."""

    __tablename__ = "individual_plans"

    id = db.Column(db.Integer, primary_key=True)
    generated_plan_id = db.Column(
        db.Integer, db.ForeignKey("generated_plans.id"), nullable=False
    )
    musician_name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(120), nullable=False)
    is_vakant = db.Column(db.Boolean, default=False)

    # DOCX + PDF als BLOB
    docx_data = db.Column(db.LargeBinary, nullable=True)
    pdf_data = db.Column(db.LargeBinary, nullable=True)

    @property
    def display_name(self):
        """Anzeigename: Name oder 'Position (vakant)'."""
        if self.is_vakant:
            return f"{self.position} (vakant)"
        return self.musician_name

    @property
    def sort_key(self):
        """Sortier-Schluessel: Nachname fuer besetzte, Position fuer vakante."""
        if self.is_vakant:
            return f"zzz_{self.position}"
        parts = self.musician_name.split()
        nachname = parts[-1] if parts else self.musician_name
        vorname = parts[0] if len(parts) > 1 else ""
        return f"{nachname}_{vorname}"

    def __repr__(self):
        return f"<IndividualPlan {self.musician_name}>"
