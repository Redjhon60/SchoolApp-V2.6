"""
Payment Receipt Generator
==========================
Generates a professional PDF receipt using ReportLab.
The school logo (assets/icons/logo.jpeg) is embedded when available.
"""

import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas

from database.db_manager import DatabaseManager


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_export_dir():
    return os.path.join(_get_base_dir(), "assets", "exports", "receipts")


def _find_logo():
    base = _get_base_dir()
    for name in ("logo.jpeg", "logo.jpg", "logo.png"):
        p = os.path.join(base, "assets", "icons", name)
        if os.path.exists(p):
            return p
    return None


def generate_receipt_pdf(payment: dict, student: dict,
                          remaining_amount: float = None,
                          logo_path: str = None) -> str:
    export_dir = _get_export_dir()
    os.makedirs(export_dir, exist_ok=True)

    db = DatabaseManager()
    school_name = db.get_setting("school_name", "Le Schéma")

    filename = f"{payment['receipt_number']}.pdf".replace("/", "-")
    path = os.path.join(export_dir, filename)

    c = rl_canvas.Canvas(path, pagesize=A4)
    W, H = A4

    # ── Header bar ──────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#2563EB"))
    c.rect(0, H - 38 * mm, W, 38 * mm, fill=True, stroke=False)

    # Logo (caller may pass one; otherwise auto-detect from assets)
    logo = logo_path or _find_logo()
    text_x = 18 * mm
    if logo and os.path.exists(logo):
        try:
            c.drawImage(logo, 12 * mm, H - 36 * mm,
                         width=30 * mm, height=30 * mm,
                         preserveAspectRatio=True, mask="auto")
            text_x = 46 * mm
        except Exception:
            pass

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(text_x, H - 16 * mm, school_name)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(text_x, H - 26 * mm, "REÇU DE PAIEMENT")
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 14 * mm, H - 16 * mm, f"N°  {payment['receipt_number']}")
    c.drawRightString(W - 14 * mm, H - 24 * mm, f"Date: {payment['payment_date']}")

    # ── Body ─────────────────────────────────────────────────────────────
    c.setFillColor(colors.black)
    y          = H - 50 * mm
    line_h     = 8  * mm
    label_x    = 18 * mm
    value_x    = 72 * mm

    full_name = f"{student.get('eleve_nom', student.get('nom',''))} " \
                f"{student.get('eleve_prenom', student.get('prenom',''))}".strip()

    fields = [
        ("Matricule",        student.get("matricule", "")),
        ("Nom et Prénom",    full_name),
        ("Classe",           student.get("classe", "")),
        ("Année scolaire",   payment.get("annee_scolaire", "")),
        ("Type de paiement", payment.get("payment_type", "")),
    ]
    if payment.get("month"):
        fields.append(("Mois concerné", payment["month"]))

    for label, value in fields:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(label_x, y, f"{label} :")
        c.setFont("Helvetica", 11)
        c.drawString(value_x, y, str(value or "-"))
        y -= line_h

    # ── Amount box ───────────────────────────────────────────────────────
    y -= 4 * mm
    c.setFillColor(colors.HexColor("#F0FDF4"))
    c.roundRect(label_x, y - 16 * mm, W - 36 * mm, 16 * mm, 3 * mm, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#16A34A"))
    c.setFont("Helvetica-Bold", 15)
    c.drawString(label_x + 6 * mm, y - 11 * mm, "Montant payé :")
    c.drawRightString(W - 20 * mm, y - 11 * mm, f"{payment.get('amount', 0):.2f} DH")
    y -= 22 * mm

    c.setFillColor(colors.black)
    if remaining_amount is not None:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(label_x, y, "Montant restant :")
        c.setFont("Helvetica", 11)
        c.drawString(value_x, y, f"{remaining_amount:.2f} DH")
        y -= line_h

    if payment.get("notes"):
        y -= 2 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(label_x, y, "Remarques :")
        y -= line_h
        c.setFont("Helvetica", 10)
        c.drawString(label_x, y, str(payment["notes"])[:100])
        y -= line_h

    # ── Signature area ───────────────────────────────────────────────────
    sig_y = 30 * mm
    c.setFont("Helvetica", 9)
    c.line(label_x, sig_y, 80 * mm, sig_y)
    c.drawString(label_x, sig_y - 5 * mm, "Signature du parent / tuteur")

    c.line(W - 80 * mm, sig_y, W - label_x, sig_y)
    c.drawString(W - 80 * mm, sig_y - 5 * mm, "Cachet et signature de l'école")

    # ── Footer ───────────────────────────────────────────────────────────
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(label_x, 14 * mm,
                  f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}  –  {school_name}")

    c.showPage()
    c.save()
    return path
