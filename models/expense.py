"""
Expense Model
=============
CRUD and aggregation for the `expenses` and `expense_payments` tables.

Expense Types: "Fixe" | "Variable"
Status:        "Payé"  | "Non Payé"

Recurring (Fixe) expenses can be bulk-generated across months via
`generate_recurring()`.  Each generated row is independent so payment
tracking works month-by-month, exactly like student & salary payments.
"""

import uuid
from datetime import datetime
from database.db_manager import DatabaseManager

SCHOOL_MONTHS = [
    "Septembre", "Octobre", "Novembre", "Décembre",
    "Janvier",   "Février", "Mars",     "Avril",    "Mai", "Juin",
]

MONTH_TO_OFFSET = {m: (i, 0 if i < 4 else 1) for i, m in enumerate(SCHOOL_MONTHS)}
# offset 0 → start_year (Sep-Dec), offset 1 → end_year (Jan-Jun)

FIXED_CATEGORIES = [
    "Loyer", "Connexion Internet", "Eau", "Électricité",
    "Assurance", "Téléphone", "Sécurité", "Abonnements",
]
VARIABLE_CATEGORIES = [
    "Fournitures scolaires", "Maintenance", "Réparations",
    "Événements", "Marketing", "Achat matériel",
    "Achat mobilier", "Transport", "Divers",
]
ALL_CATEGORIES = FIXED_CATEGORIES + VARIABLE_CATEGORIES


class Expense:

    COLUMNS = [
        "expense_type", "category", "description", "amount",
        "month", "year", "annee_scolaire", "status", "payment_date",
        "notes", "is_recurring", "recurring_group", "created_at", "updated_at",
    ]

    # ─────────────────────────────────────────────────────────────────
    # CRUD
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def create(data: dict) -> int:
        db  = DatabaseManager()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d   = dict(data)
        d.setdefault("created_at",  now)
        d.setdefault("updated_at",  now)
        d.setdefault("status",      "Non Payé")
        d.setdefault("is_recurring", 0)
        d.setdefault("recurring_group", "")

        cols   = [c for c in Expense.COLUMNS if c in d]
        values = [d[c] for c in cols]
        cur    = db.execute(
            f"INSERT INTO expenses ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})",
            values,
        )
        return cur.lastrowid

    @staticmethod
    def update(expense_id: int, data: dict):
        db  = DatabaseManager()
        d   = dict(data)
        d["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        updatable = [
            "expense_type", "category", "description", "amount",
            "month", "year", "annee_scolaire", "status", "payment_date",
            "notes", "is_recurring", "recurring_group", "updated_at",
        ]
        cols   = [c for c in updatable if c in d]
        values = [d[c] for c in cols] + [expense_id]
        db.execute(
            f"UPDATE expenses SET {', '.join(c+'=?' for c in cols)} WHERE id=?",
            values,
        )

    @staticmethod
    def delete(expense_id: int):
        DatabaseManager().execute("DELETE FROM expenses WHERE id=?", (expense_id,))

    @staticmethod
    def delete_recurring_group(group_id: str):
        """Delete all expenses in a recurring group (future only if needed)."""
        DatabaseManager().execute(
            "DELETE FROM expenses WHERE recurring_group=? AND status='Non Payé'",
            (group_id,),
        )

    @staticmethod
    def get_by_id(expense_id: int):
        return DatabaseManager().fetchone("SELECT * FROM expenses WHERE id=?", (expense_id,))

    @staticmethod
    def get_all(annee_scolaire: str = None, month: str = None, year: str = None,
                expense_type: str = None, category: str = None,
                status: str = None, search: str = None):
        db     = DatabaseManager()
        q      = "SELECT * FROM expenses WHERE 1=1"
        params = []
        if annee_scolaire:
            q += " AND annee_scolaire=?"; params.append(annee_scolaire)
        if month and month != "Tous":
            q += " AND month=?"; params.append(month)
        if year and year != "Toutes":
            q += " AND year=?"; params.append(year)
        if expense_type and expense_type != "Tous":
            q += " AND expense_type=?"; params.append(expense_type)
        if category and category != "Toutes":
            q += " AND category=?"; params.append(category)
        if status and status != "Tous":
            q += " AND status=?"; params.append(status)
        if search:
            q += " AND (category LIKE ? OR description LIKE ? OR notes LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]
        q += " ORDER BY year ASC, month ASC, category ASC"
        return db.fetchall(q, params)

    @staticmethod
    def get_unpaid(annee_scolaire: str = None, month: str = None):
        return Expense.get_all(
            annee_scolaire=annee_scolaire, month=month, status="Non Payé"
        )

    # ─────────────────────────────────────────────────────────────────
    # Recurring expense generation
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def generate_recurring(category: str, description: str, amount: float,
                            annee_scolaire: str, months: list = None,
                            notes: str = "") -> list:
        """
        Generate one expense row per school month (Sep→Jun by default,
        or the provided `months` list).  All rows share a `recurring_group`
        UUID so the whole series can be managed together.
        Returns list of created IDs.
        """
        start_year = int(annee_scolaire.split("/")[0])
        end_year   = int(annee_scolaire.split("/")[1])
        group_id   = str(uuid.uuid4())[:8]
        target_months = months if months else SCHOOL_MONTHS
        created_ids   = []

        for month in target_months:
            idx, offset = MONTH_TO_OFFSET[month]
            yr = str(start_year if offset == 0 else end_year)

            # Avoid duplicates: skip if already exists for this group/month
            existing = DatabaseManager().fetchone(
                "SELECT id FROM expenses WHERE recurring_group=? AND month=? AND year=?",
                (group_id, month, yr),
            )
            if existing:
                continue

            eid = Expense.create({
                "expense_type":     "Fixe",
                "category":         category,
                "description":      description,
                "amount":           amount,
                "month":            month,
                "year":             yr,
                "annee_scolaire":   annee_scolaire,
                "notes":            notes,
                "is_recurring":     1,
                "recurring_group":  group_id,
            })
            created_ids.append(eid)

        return created_ids

    # ─────────────────────────────────────────────────────────────────
    # Payment helpers
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def mark_paid(expense_id: int, payment_date: str):
        Expense.update(expense_id, {"status": "Payé", "payment_date": payment_date})

    @staticmethod
    def get_next_unpaid_in_group(recurring_group: str) -> dict:
        """Return the first unpaid expense in a recurring group (chronological)."""
        db   = DatabaseManager()
        rows = db.fetchall(
            "SELECT * FROM expenses WHERE recurring_group=? AND status='Non Payé' "
            "ORDER BY year ASC, month ASC",
            (recurring_group,),
        )
        if not rows:
            return None
        # sort by school month order
        def sort_key(r):
            idx = SCHOOL_MONTHS.index(r["month"]) if r["month"] in SCHOOL_MONTHS else 99
            return (r["year"], idx)
        rows.sort(key=sort_key)
        return rows[0]

    # ─────────────────────────────────────────────────────────────────
    # KPI aggregations
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def total_expenses(annee_scolaire: str = None, month: str = None,
                       year: str = None, category: str = None) -> float:
        db     = DatabaseManager()
        q      = "SELECT COALESCE(SUM(amount),0) as total FROM expenses WHERE 1=1"
        params = []
        if annee_scolaire:
            q += " AND annee_scolaire=?"; params.append(annee_scolaire)
        if month and month != "Tous":
            q += " AND month=?"; params.append(month)
        if year and year != "Toutes":
            q += " AND year=?"; params.append(year)
        if category and category != "Toutes":
            q += " AND category=?"; params.append(category)
        row = db.fetchone(q, params)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def total_paid_expenses(annee_scolaire: str = None, month: str = None,
                             year: str = None, category: str = None) -> float:
        db     = DatabaseManager()
        q      = "SELECT COALESCE(SUM(amount),0) as total FROM expenses WHERE status='Payé'"
        params = []
        if annee_scolaire:
            q += " AND annee_scolaire=?"; params.append(annee_scolaire)
        if month and month != "Tous":
            q += " AND month=?"; params.append(month)
        if year and year != "Toutes":
            q += " AND year=?"; params.append(year)
        if category and category != "Toutes":
            q += " AND category=?"; params.append(category)
        row = db.fetchone(q, params)
        return float(row["total"]) if row else 0.0

    @staticmethod
    def count_unpaid(annee_scolaire: str = None, month: str = None) -> int:
        db     = DatabaseManager()
        q      = "SELECT COUNT(*) as cnt FROM expenses WHERE status='Non Payé'"
        params = []
        if annee_scolaire:
            q += " AND annee_scolaire=?"; params.append(annee_scolaire)
        if month and month != "Tous":
            q += " AND month=?"; params.append(month)
        row = db.fetchone(q, params)
        return row["cnt"] if row else 0

    @staticmethod
    def expenses_by_category(annee_scolaire: str = None) -> list:
        db     = DatabaseManager()
        q      = ("SELECT category, COALESCE(SUM(amount),0) as total "
                  "FROM expenses WHERE 1=1")
        params = []
        if annee_scolaire:
            q += " AND annee_scolaire=?"; params.append(annee_scolaire)
        q += " GROUP BY category ORDER BY total DESC"
        rows = db.fetchall(q, params)
        return [(r["category"], float(r["total"])) for r in rows]

    @staticmethod
    def expenses_by_type(annee_scolaire: str = None) -> dict:
        db     = DatabaseManager()
        q      = ("SELECT expense_type, COALESCE(SUM(amount),0) as total "
                  "FROM expenses WHERE 1=1")
        params = []
        if annee_scolaire:
            q += " AND annee_scolaire=?"; params.append(annee_scolaire)
        q += " GROUP BY expense_type"
        rows   = db.fetchall(q, params)
        result = {"Fixe": 0.0, "Variable": 0.0}
        for r in rows:
            result[r["expense_type"]] = float(r["total"])
        return result

    @staticmethod
    def monthly_expense_evolution(annee_scolaire: str) -> list:
        """Returns [{month, paid, unpaid, total}] for all school months."""
        start_year = int(annee_scolaire.split("/")[0])
        end_year   = int(annee_scolaire.split("/")[1])
        db         = DatabaseManager()
        results    = []

        for idx, month in enumerate(SCHOOL_MONTHS):
            _, offset = MONTH_TO_OFFSET[month]
            yr = str(start_year if offset == 0 else end_year)

            paid_row = db.fetchone(
                "SELECT COALESCE(SUM(amount),0) as total FROM expenses "
                "WHERE annee_scolaire=? AND month=? AND year=? AND status='Payé'",
                (annee_scolaire, month, yr),
            )
            unpaid_row = db.fetchone(
                "SELECT COALESCE(SUM(amount),0) as total FROM expenses "
                "WHERE annee_scolaire=? AND month=? AND year=? AND status='Non Payé'",
                (annee_scolaire, month, yr),
            )
            paid   = float(paid_row["total"])   if paid_row   else 0.0
            unpaid = float(unpaid_row["total"]) if unpaid_row else 0.0
            results.append({"month": month, "paid": paid,
                            "unpaid": unpaid, "total": paid + unpaid})
        return results

    @staticmethod
    def monthly_summary(annee_scolaire: str) -> list:
        """Returns [{month, year, paid, unpaid, total}] for export/display."""
        start_year = int(annee_scolaire.split("/")[0])
        end_year   = int(annee_scolaire.split("/")[1])
        db         = DatabaseManager()
        rows       = []

        for month in SCHOOL_MONTHS:
            _, offset = MONTH_TO_OFFSET[month]
            yr    = str(start_year if offset == 0 else end_year)
            total = db.fetchone(
                "SELECT COALESCE(SUM(amount),0) as t FROM expenses "
                "WHERE annee_scolaire=? AND month=? AND year=?",
                (annee_scolaire, month, yr),
            )
            paid  = db.fetchone(
                "SELECT COALESCE(SUM(amount),0) as t FROM expenses "
                "WHERE annee_scolaire=? AND month=? AND year=? AND status='Payé'",
                (annee_scolaire, month, yr),
            )
            t = float(total["t"]) if total else 0.0
            p = float(paid["t"])  if paid  else 0.0
            rows.append({
                "month": month, "year": yr,
                "paid": p, "unpaid": t - p, "total": t,
            })
        return rows


# ─────────────────────────────────────────────────────────────────────
class ExpensePayment:
    """CRUD for expense_payments receipts."""

    @staticmethod
    def generate_receipt_number() -> str:
        db   = DatabaseManager()
        last = int(db.get_setting("last_expense_receipt_seq", "0") or "0")
        nxt  = last + 1
        db.set_setting("last_expense_receipt_seq", str(nxt))
        return f"EXP-{datetime.now().year}-{nxt:06d}"

    @staticmethod
    def create(data: dict) -> int:
        db  = DatabaseManager()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        d   = dict(data)
        d.setdefault("created_at", now)
        if not d.get("receipt_number"):
            d["receipt_number"] = ExpensePayment.generate_receipt_number()

        cols   = ["expense_id", "amount_paid", "payment_date",
                  "receipt_number", "notes", "created_at"]
        cols   = [c for c in cols if c in d]
        values = [d[c] for c in cols]
        cur    = db.execute(
            f"INSERT INTO expense_payments ({','.join(cols)}) "
            f"VALUES ({','.join(['?']*len(cols))})",
            values,
        )
        return cur.lastrowid

    @staticmethod
    def get_by_id(payment_id: int):
        return DatabaseManager().fetchone(
            "SELECT * FROM expense_payments WHERE id=?", (payment_id,)
        )

    @staticmethod
    def get_history(expense_id: int = None, month: str = None,
                    year: str = None, category: str = None):
        db     = DatabaseManager()
        q      = (
            "SELECT ep.*, e.category, e.description, e.expense_type, "
            "e.month, e.year, e.amount "
            "FROM expense_payments ep "
            "JOIN expenses e ON ep.expense_id = e.id WHERE 1=1"
        )
        params = []
        if expense_id:
            q += " AND ep.expense_id=?"; params.append(expense_id)
        if month and month != "Tous":
            q += " AND e.month=?"; params.append(month)
        if year and year != "Toutes":
            q += " AND e.year=?"; params.append(year)
        if category and category != "Toutes":
            q += " AND e.category=?"; params.append(category)
        q += " ORDER BY ep.payment_date DESC, ep.id DESC"
        return db.fetchall(q, params)

    @staticmethod
    def pay_expense(expense_id: int, amount_paid: float,
                    payment_date: str, notes: str = "") -> dict:
        """Full payment workflow: create record + mark expense as Payé."""
        pay_id  = ExpensePayment.create({
            "expense_id":   expense_id,
            "amount_paid":  amount_paid,
            "payment_date": payment_date,
            "notes":        notes,
        })
        Expense.mark_paid(expense_id, payment_date)
        return ExpensePayment.get_by_id(pay_id)
