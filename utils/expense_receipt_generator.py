"""
Expense Receipt Generator
==========================
Generates a professional PDF receipt for an expense payment.
"""

import os, sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas as rl_canvas
from database.db_manager import DatabaseManager


def _base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _export_dir():
    return os.path.join(_base_dir(), "assets", "exports", "expense_receipts")

def _find_logo():
    base = _base_dir()
    for name in ("logo.jpeg", "logo.jpg", "logo.png"):
        p = os.path.join(base, "assets", "icons", name)
        if os.path.exists(p): return p
    return None


def generate_expense_receipt_pdf(expense: dict, payment: dict) -> str:
    """
    expense keys : id, expense_type, category, description, amount, month, year
    payment keys : receipt_number, amount_paid, payment_date, notes
    """
    os.makedirs(_export_dir(), exist_ok=True)
    db          = DatabaseManager()
    school_name = db.get_setting("school_name", "Le Schéma")
    filename    = f"{payment['receipt_number']}.pdf".replace("/", "-")
    path        = os.path.join(_export_dir(), filename)

    c    = rl_canvas.Canvas(path, pagesize=A4)
    W, H = A4

    # ── Header ───────────────────────────────────────────────────────
    c.setFillColor(colors.HexColor("#7C3AED"))
    c.rect(0, H - 40*mm, W, 40*mm, fill=True, stroke=False)

    logo  = _find_logo()
    tx    = 18*mm
    if logo:
        try:
            c.drawImage(logo, 12*mm, H-38*mm, width=30*mm, height=30*mm,
                         preserveAspectRatio=True, mask="auto")
            tx = 48*mm
        except Exception:
            pass

    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(tx, H-16*mm, school_name)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(tx, H-27*mm, "REÇU DE PAIEMENT DE DÉPENSE")
    c.setFont("Helvetica", 9)
    c.drawRightString(W-14*mm, H-16*mm, f"N°  {payment['receipt_number']}")
    c.drawRightString(W-14*mm, H-25*mm, f"Date: {payment['payment_date']}")

    # ── Body ─────────────────────────────────────────────────────────
    c.setFillColor(colors.black)
    lx, vx = 18*mm, 72*mm
    lh     = 8*mm
    y      = H - 52*mm

    def section(title, yp):
        c.setFillColor(colors.HexColor("#F5F3FF"))
        c.rect(lx, yp-4*mm, W-36*mm, 8*mm, fill=True, stroke=False)
        c.setFillColor(colors.HexColor("#7C3AED"))
        c.setFont("Helvetica-Bold", 11)
        c.drawString(lx+3*mm, yp, title)
        c.setFillColor(colors.black)
        return yp - 10*mm

    def row(label, value, yp):
        c.setFont("Helvetica-Bold", 10)
        c.drawString(lx, yp, f"{label} :")
        c.setFont("Helvetica", 10)
        c.drawString(vx, yp, str(value or "-"))
        return yp - lh

    y = section("Informations de la Dépense", y)
    y = row("Référence",    f"EXP-{expense.get('id','')}", y)
    y = row("Type",         expense.get("expense_type",""),  y)
    y = row("Catégorie",    expense.get("category",""),      y)
    y = row("Description",  expense.get("description",""),   y)
    y = row("Mois / Année", f"{expense.get('month','')} {expense.get('year','')}", y)
    y -= 4*mm

    y = section("Détails du Paiement", y)
    y = row("Montant de la dépense", f"{expense.get('amount',0):,.2f} DH", y)
    y -= 4*mm

    c.setFillColor(colors.HexColor("#F5F3FF"))
    c.roundRect(lx, y-16*mm, W-36*mm, 16*mm, 3*mm, fill=True, stroke=False)
    c.setFillColor(colors.HexColor("#7C3AED"))
    c.setFont("Helvetica-Bold", 14)
    c.drawString(lx+6*mm, y-11*mm, "Montant payé :")
    c.drawRightString(W-20*mm, y-11*mm, f"{payment.get('amount_paid',0):,.2f} DH")
    y -= 22*mm
    c.setFillColor(colors.black)

    if payment.get("notes"):
        y -= 2*mm
        c.setFont("Helvetica-Bold", 10)
        c.drawString(lx, y, "Notes :")
        c.setFont("Helvetica", 10)
        c.drawString(vx, y, str(payment["notes"])[:100])
        y -= lh

    # ── Signatures ───────────────────────────────────────────────────
    sy = 35*mm
    c.setFont("Helvetica", 9)
    c.line(lx, sy, 80*mm, sy)
    c.drawString(lx, sy-5*mm, "Signature de l'école")
    c.line(W-80*mm, sy, W-lx, sy)
    c.drawString(W-80*mm, sy-5*mm, "Signature du bénéficiaire")

    # ── Footer ───────────────────────────────────────────────────────
    c.setFont("Helvetica-Oblique", 7)
    c.setFillColor(colors.grey)
    c.drawString(lx, 14*mm,
                 f"Document généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}  –  {school_name}")
    c.showPage()
    c.save()
    return path
