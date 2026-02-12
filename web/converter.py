"""DOCX zu PDF Konvertierung via LibreOffice headless."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def docx_to_pdf(docx_bytes: bytes) -> bytes:
    """Konvertiert DOCX-Bytes zu PDF-Bytes.

    Nutzt LibreOffice im headless-Modus.
    Falls LibreOffice nicht verfuegbar ist, wird None zurueckgegeben.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        docx_path = tmpdir_path / "document.docx"
        docx_path.write_bytes(docx_bytes)

        try:
            result = subprocess.run(
                [
                    "libreoffice",
                    "--headless",
                    "--convert-to", "pdf",
                    "--outdir", str(tmpdir_path),
                    str(docx_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,  # 2 Minuten Timeout
            )

            if result.returncode != 0:
                # Fallback: soffice statt libreoffice
                result = subprocess.run(
                    [
                        "soffice",
                        "--headless",
                        "--convert-to", "pdf",
                        "--outdir", str(tmpdir_path),
                        str(docx_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )

            pdf_path = tmpdir_path / "document.pdf"
            if pdf_path.exists():
                return pdf_path.read_bytes()

        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return None


def is_libreoffice_available() -> bool:
    """Prueft ob LibreOffice installiert ist."""
    for cmd in ["libreoffice", "soffice"]:
        try:
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return False
