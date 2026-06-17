"""
Employee Model
==============
CRUD operations for the `employees` table.
The `classe` column stores a comma-separated list of assigned classes
(relevant when job == "Professeur").
"""

from datetime import datetime
from database.db_manager import DatabaseManager


SCHOOL_MONTHS = [
    "Septembre", "Octobre", "Novembre", "Décembre",
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
]


class Employee:

    COLUMNS = [
        "cin", "nom", "prenom", "job", "classe", "salary",
        "start_date", "note", "statut", "date_created", "last_updated",
    ]

    # ──────────────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def create(data: dict) -> int:
        db  = DatabaseManager()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = dict(data)
        data.setdefault("date_created", now)
        data.setdefault("last_updated", now)
        data.setdefault("statut", "Actif")

        cols   = [c for c in Employee.COLUMNS if c in data]
        values = [data[c] for c in cols]
        cursor = db.execute(
            f"INSERT INTO employees ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
            values,
        )
        return cursor.lastrowid

    @staticmethod
    def update(employee_id: int, data: dict):
        db  = DatabaseManager()
        data = dict(data)
        data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        updatable = ["nom", "prenom", "job", "classe", "salary",
                     "start_date", "note", "statut", "last_updated"]
        cols   = [c for c in updatable if c in data]
        values = [data[c] for c in cols] + [employee_id]
        db.execute(
            f"UPDATE employees SET {', '.join(c+'=?' for c in cols)} WHERE id=?",
            values,
        )

    @staticmethod
    def delete(employee_id: int):
        DatabaseManager().execute("DELETE FROM employees WHERE id=?", (employee_id,))

    @staticmethod
    def get_by_id(employee_id: int):
        return DatabaseManager().fetchone("SELECT * FROM employees WHERE id=?", (employee_id,))

    @staticmethod
    def get_by_cin(cin: str):
        return DatabaseManager().fetchone("SELECT * FROM employees WHERE cin=?", (str(cin),))

    @staticmethod
    def get_all(job: str = None, classe: str = None, search: str = None,
                statut: str = "Actif"):
        db     = DatabaseManager()
        query  = "SELECT * FROM employees WHERE 1=1"
        params = []
        if statut:
            query += " AND statut=?"; params.append(statut)
        if job and job != "Tous":
            query += " AND job=?"; params.append(job)
        if classe and classe != "Toutes":
            query += " AND (classe=? OR classe LIKE ? OR classe LIKE ? OR classe LIKE ?)";
            params += [classe, f"{classe},%", f"%,{classe}", f"%,{classe},%"]
        if search:
            query += (" AND (cin LIKE ? OR nom LIKE ? OR prenom LIKE ?"
                      " OR job LIKE ? OR classe LIKE ?)")
            like = f"%{search}%"
            params += [like]*5
        query += " ORDER BY nom ASC, prenom ASC"
        return db.fetchall(query, params)

    @staticmethod
    def count_active() -> int:
        row = DatabaseManager().fetchone(
            "SELECT COUNT(*) as cnt FROM employees WHERE statut='Actif'"
        )
        return row["cnt"] if row else 0

    @staticmethod
    def get_distinct_jobs():
        rows = DatabaseManager().fetchall(
            "SELECT DISTINCT job FROM employees WHERE job!='' ORDER BY job"
        )
        return [r["job"] for r in rows]

    # ──────────────────────────────────────────────────────────────────
    # Class assignment helpers (Professeur logic)
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def get_assigned_classes(employee_id: int) -> list:
        emp = Employee.get_by_id(employee_id)
        if not emp or not emp.get("classe"):
            return []
        return [c.strip() for c in emp["classe"].split(",") if c.strip()]

    @staticmethod
    def set_assigned_classes(employee_id: int, classes: list):
        Employee.update(employee_id, {"classe": ", ".join(classes)})

    # ──────────────────────────────────────────────────────────────────
    # Salary helpers
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def get_total_salary_budget() -> float:
        row = DatabaseManager().fetchone(
            "SELECT COALESCE(SUM(salary),0) as total FROM employees WHERE statut='Actif'"
        )
        return float(row["total"]) if row else 0.0
