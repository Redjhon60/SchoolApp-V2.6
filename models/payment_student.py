"""
Payment Student Model  (unified with `students` table)
========================================================
All payment operations now read/write the same `students` table
used by Gestion des Élèves, so imported payment students appear
across ALL screens automatically.

Field mapping  payment-module ↔ students table
  nom          → eleve_nom
  prenom       → eleve_prenom
  total_a_payer → total_a_payer  (new column added via migration)
"""

from datetime import datetime
from database.db_manager import DatabaseManager
from utils.payment_constants import SCHOOL_MONTHS, STATUS_UNPAID, STATUS_NAN, STATUS_PAYE


def _row_to_payment_view(row: dict) -> dict:
    """
    Return a dict with both the native students-table field names AND
    the legacy payment-module aliases (nom/prenom) so existing view code
    keeps working with zero changes.
    """
    if not row:
        return row
    row = dict(row)
    row.setdefault("nom",   row.get("eleve_nom", ""))
    row.setdefault("prenom", row.get("eleve_prenom", ""))
    return row


class PaymentStudent:

    # ------------------------------------------------------------------
    # CRUD – thin wrappers over the unified `students` table
    # ------------------------------------------------------------------
    @staticmethod
    def create(data: dict) -> int:
        db = DatabaseManager()
        data = dict(data)
        data.setdefault("date_creation", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        data.setdefault("statut", "Actif")

        # Accept nom/prenom aliases
        if "nom" in data and "eleve_nom" not in data:
            data["eleve_nom"] = data.pop("nom")
        if "prenom" in data and "eleve_prenom" not in data:
            data["eleve_prenom"] = data.pop("prenom")
        data.setdefault("eleve_nom", "")
        data.setdefault("eleve_prenom", "")

        columns = [
            "matricule", "eleve_nom", "eleve_prenom", "classe", "inscription",
            "inscription_amount", "transport", "transport_yn", "mensualite",
            "total_a_payer", "note_date", "annee_scolaire", "date_creation", "statut",
        ]
        columns = [c for c in columns if c in data]
        placeholders = ", ".join(["?"] * len(columns))
        values = [data[c] for c in columns]

        query = f"INSERT INTO students ({', '.join(columns)}) VALUES ({placeholders})"
        cursor = db.execute(query, values)
        return cursor.lastrowid

    @staticmethod
    def update(student_id: int, data: dict):
        db = DatabaseManager()
        data = dict(data)
        if "nom" in data and "eleve_nom" not in data:
            data["eleve_nom"] = data.pop("nom")
        if "prenom" in data and "eleve_prenom" not in data:
            data["eleve_prenom"] = data.pop("prenom")

        updatable = [
            "eleve_nom", "eleve_prenom", "classe", "inscription", "inscription_amount",
            "transport", "transport_yn", "mensualite", "total_a_payer", "note_date",
        ]
        columns = [c for c in updatable if c in data]
        if not columns:
            return
        set_clause = ", ".join(f"{c} = ?" for c in columns)
        values = [data[c] for c in columns] + [student_id]
        db.execute(f"UPDATE students SET {set_clause} WHERE id = ?", values)

    @staticmethod
    def get_by_id(student_id: int):
        db = DatabaseManager()
        row = db.fetchone("SELECT * FROM students WHERE id = ?", (student_id,))
        return _row_to_payment_view(row)

    @staticmethod
    def get_by_key(matricule: str, classe: str, annee_scolaire: str):
        db = DatabaseManager()
        row = db.fetchone(
            "SELECT * FROM students WHERE matricule = ? AND classe = ? AND annee_scolaire = ?",
            (str(matricule), str(classe), str(annee_scolaire)),
        )
        return _row_to_payment_view(row)

    @staticmethod
    def search(annee_scolaire: str = None, classe: str = None, search: str = None):
        db = DatabaseManager()
        query = "SELECT * FROM students WHERE 1=1"
        params = []
        if annee_scolaire:
            query += " AND annee_scolaire = ?"
            params.append(annee_scolaire)
        if classe and classe != "Toutes":
            query += " AND classe = ?"
            params.append(classe)
        if search:
            query += (
                " AND (eleve_nom LIKE ? OR eleve_prenom LIKE ? "
                "OR matricule LIKE ? OR classe LIKE ?)"
            )
            like = f"%{search}%"
            params.extend([like, like, like, like])
        query += " ORDER BY eleve_nom ASC, eleve_prenom ASC"
        rows = db.fetchall(query, params)
        return [_row_to_payment_view(r) for r in rows]

    @staticmethod
    def get_distinct_classes(annee_scolaire: str = None):
        db = DatabaseManager()
        if annee_scolaire:
            rows = db.fetchall(
                "SELECT DISTINCT classe FROM students WHERE annee_scolaire = ? "
                "AND classe IS NOT NULL AND classe != '' ORDER BY classe",
                (annee_scolaire,),
            )
        else:
            rows = db.fetchall(
                "SELECT DISTINCT classe FROM students WHERE "
                "classe IS NOT NULL AND classe != '' ORDER BY classe"
            )
        return [r["classe"] for r in rows]

    @staticmethod
    def count_all(annee_scolaire: str = None) -> int:
        db = DatabaseManager()
        if annee_scolaire:
            row = db.fetchone(
                "SELECT COUNT(*) as cnt FROM students WHERE annee_scolaire = ?",
                (annee_scolaire,),
            )
        else:
            row = db.fetchone("SELECT COUNT(*) as cnt FROM students")
        return row["cnt"] if row else 0

    # ------------------------------------------------------------------
    # Month status helpers
    # ------------------------------------------------------------------
    @staticmethod
    def get_month_statuses(student_id: int, annee_scolaire: str) -> dict:
        db = DatabaseManager()
        rows = db.fetchall(
            "SELECT month, status FROM month_status "
            "WHERE student_id = ? AND annee_scolaire = ?",
            (student_id, annee_scolaire),
        )
        statuses = {r["month"]: r["status"] for r in rows}
        for m in SCHOOL_MONTHS:
            statuses.setdefault(m, STATUS_UNPAID)
        return statuses

    @staticmethod
    def set_month_status(student_id: int, annee_scolaire: str, month: str,
                          status: str, source: str = "app"):
        """
        source='import'  → set during Excel import (used in monthly KPI formula)
        source='app'     → set when a payment is registered in the app
        On conflict, only update status (and source if upgrading import→app).
        """
        db = DatabaseManager()
        db.execute(
            "INSERT INTO month_status (student_id, annee_scolaire, month, status, source) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(student_id, annee_scolaire, month) "
            "DO UPDATE SET status = excluded.status, source = excluded.source",
            (student_id, annee_scolaire, month, status, source),
        )

    @staticmethod
    def get_next_unpaid_month(student_id: int, annee_scolaire: str):
        statuses = PaymentStudent.get_month_statuses(student_id, annee_scolaire)
        for month in SCHOOL_MONTHS:
            if statuses.get(month) == STATUS_UNPAID:
                return month
        return None

    # ------------------------------------------------------------------
    # Total paid
    # ------------------------------------------------------------------
    @staticmethod
    def get_total_paid(student_id: int, annee_scolaire: str) -> float:
        db = DatabaseManager()
        row = db.fetchone(
            "SELECT COALESCE(SUM(amount), 0) as total FROM payments "
            "WHERE student_id = ? AND annee_scolaire = ?",
            (student_id, annee_scolaire),
        )
        return row["total"] if row else 0.0
