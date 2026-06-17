"""
Payment Excel Import  (unified students table)
===============================================
Imports the payment template (Matricule, Nom, Prénom, Classe,
Inscription, Transport, Mensualité, Total a payé, Note/Date, Year,
Septembre … Juin) directly into the `students` table so that
all imported payment-students are visible in Gestion des Élèves
and the Dashboard just like manually-registered students.
"""

import pandas as pd
from datetime import datetime

from models.payment_student import PaymentStudent
from utils.payment_constants import SCHOOL_MONTHS, parse_month_value
from database.db_manager import DatabaseManager


def _to_float(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        try:
            import pandas as pd_inner
            if pd_inner.isna(val):
                return default
        except Exception:
            pass
        return float(val)
    import re
    text = str(val).strip().upper()
    if text in ("", "GRATUIT", "NAN"):
        return 0.0
    match = re.search(r"[\d]+(\.\d+)?", text)
    return float(match.group()) if match else default


def _clean(val):
    try:
        import pandas as pd_inner
        if pd_inner.isna(val):
            return None
    except Exception:
        pass
    if isinstance(val, float) and val == int(val):
        return int(val)
    return val


def import_payments_excel(file_path: str, default_annee_scolaire: str = None):
    """
    Read the payments Excel file and upsert every row into the unified
    `students` table, then store month statuses.

    Returns:
        {students_created, students_updated, months_set, errors}
    """
    df = pd.read_excel(file_path)

    summary = {"students_created": 0, "students_updated": 0,
                "months_set": 0, "errors": []}

    for idx, row in df.iterrows():
        try:
            matricule  = _clean(row.get("Matricule"))
            nom        = _clean(row.get("Nom"))
            prenom     = _clean(row.get("Prénom"))
            classe     = _clean(row.get("Classe"))
            annee      = _clean(row.get("Year")) or default_annee_scolaire

            if matricule is None or nom is None or annee is None:
                summary["errors"].append(
                    f"Ligne {idx + 2}: Matricule, Nom ou Year manquant."
                )
                continue

            matricule = str(matricule)
            annee     = str(annee)
            classe    = str(classe) if classe is not None else ""

            transport_val = _to_float(row.get("Transport"))
            transport_yn  = "Y" if transport_val > 0 else "N"

            insc_amount = _to_float(row.get("Inscription"))
            record = {
                "eleve_nom":          str(nom),
                "eleve_prenom":       str(prenom) if prenom is not None else "",
                "classe":             classe,
                "inscription":        str(_clean(row.get("Inscription")) or ""),
                "inscription_amount": insc_amount,
                "transport_yn":       transport_yn,
                "transport":          transport_val,
                "mensualite":         _to_float(row.get("Mensualité")),
                "total_a_payer":      _to_float(row.get("Total a payé")),
                "note_date":          str(_clean(row.get("Note/Date")) or ""),
                "annee_scolaire":     annee,
                "statut":             "Actif",
            }

            existing = PaymentStudent.get_by_key(matricule, classe, annee)
            if existing:
                PaymentStudent.update(existing["id"], record)
                student_id = existing["id"]
                summary["students_updated"] += 1
            else:
                record["matricule"] = matricule
                student_id = PaymentStudent.create(record)
                summary["students_created"] += 1

            # Month statuses
            for month in SCHOOL_MONTHS:
                status = parse_month_value(row.get(month))
                PaymentStudent.set_month_status(
                    student_id, annee, month, status, source="import"
                )
                summary["months_set"] += 1

        except Exception as e:
            summary["errors"].append(f"Ligne {idx + 2}: {e}")

    return summary
