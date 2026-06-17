"""
Payment Model
=============
All queries reference the unified `students` table via `student_id`.

KPI FORMULAS (per spec):
─────────────────────────────────────────────────────────────────────
1. Revenus d'inscription  (imported)
   = SUM(students.inscription_amount)  for matching year/class filters
   + SUM(payments.amount WHERE payment_type='Inscription')  (app-created)

2. Revenus encaissés (monthly income)
   = SUM(students.total_a_payer WHERE month_status[selected_month]='PAYE')
   + SUM(payments.amount WHERE payment_type IN ('Mensualité','Transport')
         AND payment_date falls in selected month)  (app-created)
   Displayed as:  encaissé / total
   where total = SUM(students.total_a_payer) for matching filters (all students)

3. Both KPIs respect School Year / Class / Month filters.
─────────────────────────────────────────────────────────────────────
"""

from datetime import datetime
from database.db_manager import DatabaseManager
from utils.payment_constants import SCHOOL_MONTHS, MONTH_CALENDAR_MAP, STATUS_PAYE
from models.payment_student import PaymentStudent


class Payment:

    # ──────────────────────────────────────────────────────────────────
    # Receipt numbering
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def generate_receipt_number() -> str:
        db = DatabaseManager()
        last = int(db.get_setting("last_receipt_seq", "0") or "0")
        nxt  = last + 1
        db.set_setting("last_receipt_seq", str(nxt))
        return f"REC-{datetime.now().year}-{nxt:06d}"

    # ──────────────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def create(data: dict) -> int:
        db = DatabaseManager()
        data = dict(data)
        data.setdefault("date_creation", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if not data.get("receipt_number"):
            data["receipt_number"] = Payment.generate_receipt_number()

        cols = [
            "student_id", "annee_scolaire", "payment_type", "month",
            "amount", "payment_date", "notes", "receipt_number", "date_creation",
        ]
        cols   = [c for c in cols if c in data]
        values = [data[c] for c in cols]
        cursor = db.execute(
            f"INSERT INTO payments ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
            values,
        )
        return cursor.lastrowid

    @staticmethod
    def get_by_id(payment_id: int):
        db = DatabaseManager()
        return db.fetchone("SELECT * FROM payments WHERE id = ?", (payment_id,))

    @staticmethod
    def get_history(student_id: int, annee_scolaire: str = None):
        db = DatabaseManager()
        if annee_scolaire:
            return db.fetchall(
                "SELECT * FROM payments WHERE student_id=? AND annee_scolaire=? "
                "ORDER BY payment_date DESC, id DESC",
                (student_id, annee_scolaire),
            )
        return db.fetchall(
            "SELECT * FROM payments WHERE student_id=? ORDER BY payment_date DESC, id DESC",
            (student_id,),
        )

    # ──────────────────────────────────────────────────────────────────
    # Full save workflow
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def register_payment(student_id: int, annee_scolaire: str, payment_type: str,
                          month: str, amount: float, payment_date: str,
                          notes: str = "") -> dict:
        pid = Payment.create({
            "student_id":      student_id,
            "annee_scolaire":  annee_scolaire,
            "payment_type":    payment_type,
            "month":           month or None,
            "amount":          amount,
            "payment_date":    payment_date,
            "notes":           notes,
        })
        if month and payment_type == "Mensualité":
            PaymentStudent.set_month_status(
                student_id, annee_scolaire, month, STATUS_PAYE, source="app"
            )
        return Payment.get_by_id(pid)

    # ──────────────────────────────────────────────────────────────────
    # ── KPI 1: Revenus d'inscription ──────────────────────────────────
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _class_filter(classe: str) -> bool:
        """Return True if the class filter should be applied."""
        return bool(classe) and classe not in ("Toutes", "")

    @staticmethod
    def inscription_revenue_imported(annee_scolaire: str, classe: str = None) -> float:
        """
        SUM(students.inscription_amount) for the given year/class.
        This captures the Inscription fees stored when Excel was imported.
        """
        db = DatabaseManager()
        q  = ("SELECT COALESCE(SUM(inscription_amount),0) as total "
              "FROM students WHERE annee_scolaire=?")
        p  = [annee_scolaire]
        if Payment._class_filter(classe):
            q += " AND classe=?"; p.append(classe)
        row = db.fetchone(q, p)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def inscription_revenue_app(annee_scolaire: str, classe: str = None) -> float:
        """
        SUM(payments.amount WHERE payment_type='Inscription') —
        app-created inscription payments.
        """
        db = DatabaseManager()
        q  = ("SELECT COALESCE(SUM(p.amount),0) as total "
              "FROM payments p JOIN students s ON p.student_id=s.id "
              "WHERE p.annee_scolaire=? AND p.payment_type='Inscription'")
        p  = [annee_scolaire]
        if Payment._class_filter(classe):
            q += " AND s.classe=?"; p.append(classe)
        row = db.fetchone(q, p)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def total_inscription_revenue(annee_scolaire: str, classe: str = None) -> float:
        """
        Combined inscription revenue:
        SUM(imported inscription_amount) + SUM(app Inscription payments)
        """
        return (Payment.inscription_revenue_imported(annee_scolaire, classe) +
                Payment.inscription_revenue_app(annee_scolaire, classe))

    @staticmethod
    def total_inscription_grand_total(annee_scolaire: str) -> float:
        """Total inscription for ALL classes (denominator for 'x / total' display)."""
        return Payment.total_inscription_revenue(annee_scolaire, None)

    # ──────────────────────────────────────────────────────────────────
    # ── KPI 2: Revenus encaissés (monthly) ───────────────────────────
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def monthly_revenue_imported(annee_scolaire: str, month_name: str,
                                  classe: str = None) -> float:
        """
        SUM(students.total_a_payer) WHERE month_status[month_name] = 'PAYE'
        AND source = 'import'  (i.e., marked as paid during Excel import).
        App-created payments are excluded here to avoid double-counting.
        """
        db = DatabaseManager()
        q  = (
            "SELECT COALESCE(SUM(s.total_a_payer),0) as total "
            "FROM month_status ms "
            "JOIN students s ON ms.student_id=s.id "
            "WHERE ms.annee_scolaire=? AND ms.month=? "
            "AND ms.status='PAYE' AND ms.source='import'"
        )
        p  = [annee_scolaire, month_name]
        if Payment._class_filter(classe):
            q += " AND s.classe=?"; p.append(classe)
        row = db.fetchone(q, p)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def monthly_revenue_app(annee_scolaire: str, cal_year: int, cal_month: int,
                             classe: str = None) -> float:
        """
        SUM(payments.amount) for Mensualité + Transport payments whose
        payment_date falls in the given calendar year/month.
        These are app-created payments (not from Excel import).
        """
        db = DatabaseManager()
        pattern = f"{cal_year:04d}-{cal_month:02d}%"
        q = (
            "SELECT COALESCE(SUM(p.amount),0) as total "
            "FROM payments p JOIN students s ON p.student_id=s.id "
            "WHERE p.annee_scolaire=? AND p.payment_date LIKE ? "
            "AND p.payment_type IN ('Mensualité','Transport')"
        )
        p = [annee_scolaire, pattern]
        if Payment._class_filter(classe):
            q += " AND s.classe=?"; p.append(classe)
        row = db.fetchone(q, p)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def monthly_revenue_total(annee_scolaire: str, month_name: str,
                               classe: str = None) -> float:
        """
        Full monthly revenue:
          imported (month_status=PAYE → total_a_payer)
        + app-created (Mensualité/Transport payments in that calendar month)
        """
        cal_month, offset = MONTH_CALENDAR_MAP.get(month_name, (1, 1))
        start_year = int(annee_scolaire.split("/")[0])
        end_year   = int(annee_scolaire.split("/")[1])
        cal_year   = start_year if offset == 0 else end_year

        return (
            Payment.monthly_revenue_imported(annee_scolaire, month_name, classe) +
            Payment.monthly_revenue_app(annee_scolaire, cal_year, cal_month, classe)
        )

    @staticmethod
    def total_a_payer_sum(annee_scolaire: str, classe: str = None) -> float:
        """
        SUM(students.total_a_payer) — grand total revenue for all students.
        Used as the denominator in 'encaissé / total' display.
        """
        db = DatabaseManager()
        q  = ("SELECT COALESCE(SUM(total_a_payer),0) as total "
              "FROM students WHERE annee_scolaire=?")
        p  = [annee_scolaire]
        if Payment._class_filter(classe):
            q += " AND classe=?"; p.append(classe)
        row = db.fetchone(q, p)
        return float(row["total"]) if row else 0.0

    # Kept for backward compatibility with dashboard chart functions
    @staticmethod
    def monthly_income(annee_scolaire: str, cal_year: int, cal_month: int,
                        classe: str = None) -> float:
        """Alias: app-only monthly payments (used by charts)."""
        return Payment.monthly_revenue_app(annee_scolaire, cal_year, cal_month, classe)

    # ──────────────────────────────────────────────────────────────────
    # ── Dashboard charts ──────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def monthly_income_evolution(annee_scolaire: str, classe: str = None):
        """
        Returns per-month breakdown for the income evolution line chart.
        {month, inscription, mensualite, transport, total}
        """
        db         = DatabaseManager()
        start_year = int(annee_scolaire.split("/")[0])
        end_year   = int(annee_scolaire.split("/")[1])
        results    = []

        for month_name in SCHOOL_MONTHS:
            cal_month, offset = MONTH_CALENDAR_MAP[month_name]
            cal_year  = start_year if offset == 0 else end_year
            pattern   = f"{cal_year:04d}-{cal_month:02d}%"

            row_data = {"month": month_name}
            for ptype, key in (
                ("Inscription", "inscription"),
                ("Mensualité",  "mensualite"),
                ("Transport",   "transport"),
            ):
                q = (
                    "SELECT COALESCE(SUM(p.amount),0) as total FROM payments p "
                    "JOIN students s ON p.student_id=s.id "
                    "WHERE p.annee_scolaire=? AND p.payment_date LIKE ? AND p.payment_type=?"
                )
                params = [annee_scolaire, pattern, ptype]
                if Payment._class_filter(classe):
                    q += " AND s.classe=?"; params.append(classe)
                row = db.fetchone(q, params)
                row_data[key] = float(row["total"]) if row else 0.0

            row_data["total"] = sum(row_data[k] for k in ("inscription", "mensualite", "transport"))
            results.append(row_data)

        return results

    @staticmethod
    def payment_status_distribution(annee_scolaire: str, classe: str = None):
        from utils.payment_constants import STATUS_PAYE, STATUS_UNPAID, STATUS_NAN
        db = DatabaseManager()
        q  = (
            "SELECT ms.status, COUNT(*) as cnt FROM month_status ms "
            "JOIN students s ON ms.student_id=s.id WHERE ms.annee_scolaire=?"
        )
        p = [annee_scolaire]
        if Payment._class_filter(classe):
            q += " AND s.classe=?"; p.append(classe)
        q += " GROUP BY ms.status"

        rows   = db.fetchall(q, p)
        result = {STATUS_PAYE: 0, STATUS_UNPAID: 0, STATUS_NAN: 0}
        for r in rows:
            if r["status"] in result:
                result[r["status"]] = r["cnt"]
        return result

    @staticmethod
    def income_by_class(annee_scolaire: str):
        """Total a payé per class (from students table, not payments)."""
        db   = DatabaseManager()
        rows = db.fetchall(
            "SELECT classe, COALESCE(SUM(total_a_payer),0) as total "
            "FROM students WHERE annee_scolaire=? "
            "GROUP BY classe ORDER BY classe",
            (annee_scolaire,),
        )
        return [(r["classe"] or "N/A", float(r["total"])) for r in rows]

    # ──────────────────────────────────────────────────────────────────
    # Debug helper
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def debug_kpi(annee_scolaire: str, month_name: str, classe: str = None) -> dict:
        """
        Returns a breakdown dict for the two KPI cards so values can
        be verified in logs or a debug panel.
        """
        imp_insc  = Payment.inscription_revenue_imported(annee_scolaire, classe)
        app_insc  = Payment.inscription_revenue_app(annee_scolaire, classe)
        total_insc_grand = Payment.total_inscription_grand_total(annee_scolaire)

        imp_monthly = Payment.monthly_revenue_imported(annee_scolaire, month_name, classe)
        cal_month, offset = MONTH_CALENDAR_MAP.get(month_name, (1, 1))
        cal_year = int(annee_scolaire.split("/")[offset])
        app_monthly = Payment.monthly_revenue_app(annee_scolaire, cal_year, cal_month, classe)

        total_a_payer = Payment.total_a_payer_sum(annee_scolaire, classe)
        grand_total_a_payer = Payment.total_a_payer_sum(annee_scolaire, None)

        return {
            "inscription": {
                "imported":         imp_insc,
                "app_created":      app_insc,
                "total":            imp_insc + app_insc,
                "grand_total_all_classes": total_insc_grand,
                "display":          f"{imp_insc + app_insc:,.0f} / {total_insc_grand:,.0f}",
            },
            "monthly": {
                "month":            month_name,
                "imported_paye":    imp_monthly,
                "app_created":      app_monthly,
                "total":            imp_monthly + app_monthly,
                "total_a_payer":    total_a_payer,
                "grand_total_a_payer": grand_total_a_payer,
                "display":          f"{imp_monthly + app_monthly:,.0f} / {total_a_payer:,.0f}",
            },
        }
