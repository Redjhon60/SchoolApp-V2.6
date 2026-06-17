"""
Employee Excel Import / Export
================================
Handles reading from / writing to the employee Excel template:
CIN | Nom | Prénom | Job | Class | Salary | Start date | Note
"""

import pandas as pd
from datetime import datetime
from models.employee import Employee


EXCEL_COLS = ["CIN", "Nom", "Prénom", "Job", "Class", "Salary", "Start date", "Note"]

DB_MAP = {
    "CIN":        "cin",
    "Nom":        "nom",
    "Prénom":     "prenom",
    "Job":        "job",
    "Class":      "classe",
    "Salary":     "salary",
    "Start date": "start_date",
    "Note":       "note",
}


def _clean(val):
    if pd.isna(val):
        return None
    return val


def _to_float(val, default=0.0):
    if val is None:
        return default
    try:
        if pd.isna(val):
            return default
    except Exception:
        pass
    try:
        return float(str(val).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return default


def import_employees_excel(file_path: str):
    """
    Import employees from Excel. Updates by CIN (unique key).
    Returns {created, updated, errors}.
    """
    df = pd.read_excel(file_path)

    # Normalise column names (strip whitespace)
    df.columns = [c.strip() for c in df.columns]

    summary = {"created": 0, "updated": 0, "errors": []}

    for idx, row in df.iterrows():
        try:
            cin = _clean(row.get("CIN"))
            nom = _clean(row.get("Nom"))
            if cin is None or nom is None:
                summary["errors"].append(f"Ligne {idx+2}: CIN ou Nom manquant.")
                continue

            cin = str(cin).strip()
            record = {
                "cin":        cin,
                "nom":        str(nom).strip(),
                "prenom":     str(_clean(row.get("Prénom")) or "").strip(),
                "job":        str(_clean(row.get("Job")) or "").strip(),
                "classe":     str(_clean(row.get("Class")) or "").strip(),
                "salary":     _to_float(row.get("Salary")),
                "start_date": str(_clean(row.get("Start date")) or "").strip(),
                "note":       str(_clean(row.get("Note")) or "").strip(),
            }

            existing = Employee.get_by_cin(cin)
            if existing:
                Employee.update(existing["id"], record)
                summary["updated"] += 1
            else:
                Employee.create(record)
                summary["created"] += 1

        except Exception as e:
            summary["errors"].append(f"Ligne {idx+2}: {e}")

    return summary


def export_employees_excel(employees: list, file_path: str) -> str:
    """Export list of employee dicts to Excel."""
    rows = []
    for e in employees:
        rows.append({
            "CIN":        e.get("cin", ""),
            "Nom":        e.get("nom", ""),
            "Prénom":     e.get("prenom", ""),
            "Job":        e.get("job", ""),
            "Class":      e.get("classe", ""),
            "Salary":     e.get("salary", 0),
            "Start date": e.get("start_date", ""),
            "Note":       e.get("note", ""),
        })
    pd.DataFrame(rows, columns=EXCEL_COLS).to_excel(file_path, index=False)
    return file_path


def generate_sample_employee_excel(file_path: str) -> str:
    """Write a sample template file."""
    sample = [
        {"CIN": "AB123456", "Nom": "ALAOUI", "Prénom": "KARIM",
         "Job": "Professeur", "Class": "CE1, CE2", "Salary": 5000,
         "Start date": "2023-09-01", "Note": ""},
        {"CIN": "CD789012", "Nom": "BENALI", "Prénom": "SAMIRA",
         "Job": "Directeur", "Class": "", "Salary": 8000,
         "Start date": "2020-01-01", "Note": ""},
        {"CIN": "EF345678", "Nom": "RACHIDI", "Prénom": "YOUSSEF",
         "Job": "Surveillant", "Class": "", "Salary": 3500,
         "Start date": "2024-09-01", "Note": ""},
    ]
    pd.DataFrame(sample, columns=EXCEL_COLS).to_excel(file_path, index=False)
    return file_path
