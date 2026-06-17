"""
Salary Payment Proof Generator
================================
Generates a professional PDF salary payment slip (bulletin de salaire)
with school logo, employee info, payment details and signature areas.
"""

import os
import sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Table, TableStyle

from database.db_manager import DatabaseManager


def _get_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _get_export_dir():
    return os.path.join(_get_base_dir(), "assets", "exports", "salary_proofs")


def _find_logo():
    base = _get_base_dir()
    for name in ("logo.jpeg", "logo.jpg", "logo.png"):
        p = os.path.join(base, "assets", "icons", name)
        if os.path.exists(p):
            return p
    return None


def generate_salary_proof_pdf(payment: dict, employee: dict) -> str:
    """
    Generate a salary payment proof PDF.
    `payment` keys: receipt_number, payment_month, payment_year,
                    monthly_salary, amount_paid, payment_date, notes
    `employee` keys: cin, nom, prenom, job, classe
    Returns the file path.
    """
    export_dir = _get_export_dir()
    os.makedirs(export_dir, exist_ok=True)

    db          = DatabaseManager()
    school_name = db.get_setting("school_name", "Le Schéma")

    filename = f"{payment['receipt_number']}.pdf".replace("/", "-")
    path     = os.path.join(export_dir, filename)

    c   = rl_canvas.Canvas(path, pagesize=A4)
    W, H = A4

    # ── Header bar ──────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#2563EB"))
    c.rect(0, H - 40 * mm, W, 40 * mm, fill=True, stroke=False)

    logo = _find_logo()
    text_x = 18 * mm
    if logo:
        try:
            c.drawImage(logo, 12 * mm, H - 38 * mm, width=30 * mm, height=30 * mm,
                         preserveAspectRatio=True, mask="auto")
            text_x = 48 * mm
        except Exception:
            pass

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(text_x, H - 17 * mm, school_name)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(text_x, H - 27 * mm, "BULLETIN DE PAIEMENT DE SALAIRE")
    c.setFont("Helvetica", 9)
    c.drawRightString(W - 14 * mm, H - 16 * mm, f"N°  {payment['receipt_number']}")
    c.drawRightString(W - 14 * mm, H - 25 * mm, f"Date: {payment['payment_date']}")

    # ── Section: Informations de l'employé ─────────────────────────────
    y       = H - 52 * mm
    label_x = 18 * mm
    value_x = 72 * mm
    lh      = 8  * mm

    def section_header(title, ypos):
        c.setFillColor(colors.HexColor("#EFF6FF"))
        c.rect(label_x, ypos - 4 * mm, W - 36 * mm, 8 * mm, fill=True, stroke=False)
        c.setFillColor(colors.HexColor("#2563EB"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(label_x + 3 * mm, ypos, title)
        c.setFillColor(colors.black)
        return ypos - 10 * mm

    def field_row(label, value, ypos):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(label_x, ypos, f"{label} :")
        c.setFont("Helvetica", 10)
        c.drawString(value_x, ypos, str(value or "-"))
        return ypos - lh

    y = section_header("Informations de l'Employé", y)
    y = field_row("CIN",              employee.get("cin", ""),    y)
    y = field_row("Nom",              employee.get("nom", ""),    y)
    y = field_row("Prénom",           employee.get("prenom", ""), y)
    y = field_row("Poste / Fonction", employee.get("job", ""),    y)
    classes = employee.get("classe", "")
    if classes:
        y = field_row("Classes assignées", classes, y)
    y -= 4 * mm

    # ── Section: Détails du paiement ─────────────────────────────────
    y = section_header("Détails du Paiement", y)
    y = field_row("Mois de salaire",  payment.get("payment_month", ""), y)
    y = field_row("Année",            payment.get("payment_year", ""),  y)
    y = field_row("Salaire mensuel",  f"{payment.get('monthly_salary', 0):,.2f} DH", y)

    y -= 4 * mm
    c.setFillColor(colors.HexColor("#F0FDF4"))
    c.roundRect(label_x, y - 16 * mm, W - 36 * mm, 16 * mm, 3 * mm, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#16A34A"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(label_x + 6 * mm, y - 11 * mm, "Montant payé :")
    c.drawRightString(W - 20 * mm, y - 11 * mm, f"{payment.get('amount_paid', 0):,.2f} DH")
    y -= 22 * mm
    c.setFillColor(colors.black)

    if payment.get("notes"):
        y -= 2 * mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(label_x, y, "Notes :")
        c.setFont("Helvetica", 10)
        c.drawString(value_x, y, str(payment["notes"])[:100])
        y -= lh

    # ── Signature area ───────────────────────────────────────────────
    sig_y = 35 * mm
    c.setFont("Helvetica", 9)
    c.line(label_x, sig_y, 80 * mm, sig_y)
    c.drawString(label_x, sig_y - 5 * mm, "Signature de l'employé")

    c.line(W - 80 * mm, sig_y, W - label_x, sig_y)
    c.drawString(W - 80 * mm, sig_y - 5 * mm, "Cachet et signature de l'école")

    # ── Footer ───────────────────────────────────────────────────────
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(
        label_x, 14 * mm,
        f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}  –  {school_name}"
    )

    c.showPage()
    c.save()
    return path
