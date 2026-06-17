"""
SalaryPayment Model
====================
Manages monthly salary payment records and provides aggregations
for the dashboard salary KPI.
"""

from datetime import datetime
from database.db_manager import DatabaseManager
from models.employee import Employee, SCHOOL_MONTHS


MONTH_YEAR_CALENDAR = {
    "Septembre": (9, 0), "Octobre": (10, 0), "Novembre": (11, 0),
    "Décembre": (12, 0), "Janvier": (1, 1), "Février": (2, 1),
    "Mars": (3, 1), "Avril": (4, 1), "Mai": (5, 1), "Juin": (6, 1),
}


class SalaryPayment:

    # ──────────────────────────────────────────────────────────────────
    # Receipt numbering
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def generate_receipt_number() -> str:
        db   = DatabaseManager()
        last = int(db.get_setting("last_salary_receipt_seq", "0") or "0")
        nxt  = last + 1
        db.set_setting("last_salary_receipt_seq", str(nxt))
        return f"SAL-{datetime.now().year}-{nxt:06d}"

    # ──────────────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def create(data: dict) -> int:
        db  = DatabaseManager()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = dict(data)
        data.setdefault("created_at", now)
        if not data.get("receipt_number"):
            data["receipt_number"] = SalaryPayment.generate_receipt_number()

        cols = [
            "receipt_number", "employee_id", "cin", "nom", "prenom", "job",
            "assigned_classes", "monthly_salary", "payment_month", "payment_year",
            "amount_paid", "payment_date", "notes", "created_at",
        ]
        cols   = [c for c in cols if c in data]
        values = [data[c] for c in cols]
        cursor = db.execute(
            f"INSERT INTO salary_payments ({','.join(cols)}) "
            f"VALUES ({','.join(['?']*len(cols))})",
            values,
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(payment_id: int):
        return DatabaseManager().fetchone(
            "SELECT * FROM salary_payments WHERE id=?", (payment_id,)
        )

    @staticmethod
    def get_history(employee_id: int = None, job: str = None,
                    month: str = None, year: str = None):
        db     = DatabaseManager()
        query  = "SELECT * FROM salary_payments WHERE 1=1"
        params = []
        if employee_id:
            query += " AND employee_id=?"; params.append(employee_id)
        if job and job != "Tous":
            query += " AND job=?"; params.append(job)
        if month:
            query += " AND payment_month=?"; params.append(month)
        if year:
            query += " AND payment_year=?"; params.append(year)
        query += " ORDER BY payment_date DESC, id DESC"
        return db.fetchall(query, params)

    @staticmethod
    def is_month_paid(employee_id: int, month: str, year: str) -> bool:
        row = DatabaseManager().fetchone(
            "SELECT id FROM salary_payments WHERE employee_id=? "
            "AND payment_month=? AND payment_year=?",
            (employee_id, month, year),
        )
        return row is not None

    @staticmethod
    def get_next_unpaid_month(employee_id: int, school_year: str) -> tuple:
        """
        Return (month_name, year_str) for the first unpaid salary month
        in the given school year (Sep → Jun), or (None, None) if all paid.
        """
        start_year = int(school_year.split("/")[0])
        end_year   = int(school_year.split("/")[1])
        for month in SCHOOL_MONTHS:
            _, offset = MONTH_YEAR_CALENDAR[month]
            yr = start_year if offset == 0 else end_year
            if not SalaryPayment.is_month_paid(employee_id, month, str(yr)):
                return month, str(yr)
        return None, None

    @staticmethod
    def get_paid_months(employee_id: int, school_year: str) -> dict:
        """Return {month_name: True/False} for all 10 school months."""
        start_year = int(school_year.split("/")[0])
        end_year   = int(school_year.split("/")[1])
        result = {}
        for month in SCHOOL_MONTHS:
            _, offset = MONTH_YEAR_CALENDAR[month]
            yr = start_year if offset == 0 else end_year
            result[month] = SalaryPayment.is_month_paid(employee_id, month, str(yr))
        return result

    # ──────────────────────────────────────────────────────────────────
    # Dashboard KPIs
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def total_paid(month: str = None, year: str = None, job: str = None) -> float:
        db     = DatabaseManager()
        query  = "SELECT COALESCE(SUM(amount_paid),0) as total FROM salary_payments WHERE 1=1"
        params = []
        if month:
            query += " AND payment_month=?"; params.append(month)
        if year:
            query += " AND payment_year=?"; params.append(year)
        if job and job != "Tous":
            query += " AND job=?"; params.append(job)
        row = db.fetchone(query, params)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def total_salary_budget(job: str = None) -> float:
        db     = DatabaseManager()
        query  = "SELECT COALESCE(SUM(salary),0) as total FROM employees WHERE statut='Actif'"
        params = []
        if job and job != "Tous":
            query += " AND job=?"; params.append(job)
        row = db.fetchone(query, params)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def salary_progress_by_month(school_year: str, job: str = None) -> list:
        """
        Returns list of {month, paid, unpaid} for the salary progress chart.
        """
        start_year = int(school_year.split("/")[0])
        end_year   = int(school_year.split("/")[1])
        db         = DatabaseManager()
        results    = []

        # Total active employees (optionally filtered by job)
        emp_q = "SELECT COUNT(*) as cnt, COALESCE(SUM(salary),0) as budget FROM employees WHERE statut='Actif'"
        emp_p = []
        if job and job != "Tous":
            emp_q += " AND job=?"; emp_p.append(job)
        emp_row = db.fetchone(emp_q, emp_p)
        total_budget = float(emp_row["budget"]) if emp_row else 0.0

        for month in SCHOOL_MONTHS:
            _, offset = MONTH_YEAR_CALENDAR[month]
            yr = start_year if offset == 0 else end_year

            q = ("SELECT COALESCE(SUM(amount_paid),0) as paid "
                 "FROM salary_payments WHERE payment_month=? AND payment_year=?")
            p = [month, str(yr)]
            if job and job != "Tous":
                q += " AND job=?"; p.append(job)
            row = db.fetchone(q, p)
            paid = float(row["paid"]) if row else 0.0
            results.append({
                "month": month, "paid": paid,
                "unpaid": max(total_budget - paid, 0),
            })

        return results
