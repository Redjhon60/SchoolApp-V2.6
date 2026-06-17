"""
Database Manager
=================
Singleton SQLite manager.  Handles the unified schema used by all
modules: students (= also payment_students), month_status, payments,
receipts, settings.

On first open, fresh tables are created.
On upgrade from older versions the _migrate_* helpers transparently
rebuild the schema and move existing data, so no data is lost.
"""

import sqlite3
import os
import sys
import shutil
from datetime import datetime


def _get_app_data_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "data")


DB_DIR    = _get_app_data_dir()
DB_PATH   = os.path.join(DB_DIR, "school.db")
BACKUP_DIR = os.path.join(DB_DIR, "backups")


class DatabaseManager:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        os.makedirs(DB_DIR, exist_ok=True)
        os.makedirs(BACKUP_DIR, exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate_and_create()
        self._initialized = True

    # ──────────────────────────────────────────────────────────────────
    # Schema boot  (migration-aware)
    # ──────────────────────────────────────────────────────────────────
    def _migrate_and_create(self):
        """
        Run all schema steps inside a single transaction-like sequence.
        Idempotent: safe to call on both fresh and existing databases.
        """
        c = self.conn.cursor()

        # ── Step 1: create / upgrade students table ──────────────────
        self._ensure_students_table(c)

        # ── Step 2: create / upgrade month_status table ──────────────
        self._ensure_month_status_table(c)

        # ── Step 3: create / upgrade payments table ───────────────────
        self._ensure_payments_table(c)

        # ── Step 4: receipts & settings (always additive) ─────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS receipts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_number TEXT UNIQUE NOT NULL,
                payment_id     INTEGER NOT NULL,
                file_path      TEXT,
                date_creation  TEXT,
                FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        defaults = {
            "current_school_year": "2025/2026",
            "next_school_year":    "2026/2027",
            "theme":               "Light",
            "school_name":         "Le Schéma",
            "last_receipt_seq":    "0",
        }
        for k, v in defaults.items():
            c.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v)
            )

        # ── Step 5: migrate legacy payment_students data ───────────────
        self._migrate_payment_students_table(c)

        # ── Step 6: additive column upgrades ──────────────────────────
        self._ensure_month_status_source_col(c)

        # ── Step 7: employee & salary tables ──────────────────────────
        self._ensure_employee_tables(c)

        # ── Step 8: expense tables ─────────────────────────────────────
        self._ensure_expense_tables(c)

        self.conn.commit()

    def _ensure_employee_tables(self, c):
        """Create employee and salary_payments tables (idempotent)."""
        c.execute("""
            CREATE TABLE IF NOT EXISTS employees (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                cin          TEXT    UNIQUE NOT NULL,
                nom          TEXT    NOT NULL,
                prenom       TEXT    NOT NULL DEFAULT '',
                job          TEXT    NOT NULL DEFAULT '',
                classe       TEXT    DEFAULT '',
                salary       REAL    DEFAULT 0,
                start_date   TEXT    DEFAULT '',
                note         TEXT    DEFAULT '',
                statut       TEXT    DEFAULT 'Actif',
                date_created TEXT,
                last_updated TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_emp_cin ON employees(cin)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_emp_job ON employees(job)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS salary_payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                receipt_number  TEXT    UNIQUE,
                employee_id     INTEGER NOT NULL,
                cin             TEXT    NOT NULL,
                nom             TEXT    NOT NULL,
                prenom          TEXT    DEFAULT '',
                job             TEXT    DEFAULT '',
                assigned_classes TEXT   DEFAULT '',
                monthly_salary  REAL    DEFAULT 0,
                payment_month   TEXT    NOT NULL,
                payment_year    TEXT    NOT NULL,
                amount_paid     REAL    DEFAULT 0,
                payment_date    TEXT    NOT NULL,
                notes           TEXT    DEFAULT '',
                created_at      TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_sal_emp ON salary_payments(employee_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_sal_month ON salary_payments(payment_month, payment_year)")

        # Settings: last salary receipt sequence
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_salary_receipt_seq','0')")
        self.conn.commit()

    def _ensure_expense_tables(self, c):
        """Create expenses and expense_payments tables (idempotent)."""
        c.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_type   TEXT    NOT NULL DEFAULT 'Fixe',
                category       TEXT    NOT NULL DEFAULT '',
                description    TEXT    DEFAULT '',
                amount         REAL    DEFAULT 0,
                month          TEXT    NOT NULL DEFAULT '',
                year           TEXT    NOT NULL DEFAULT '',
                annee_scolaire TEXT    DEFAULT '',
                status         TEXT    DEFAULT 'Non Payé',
                payment_date   TEXT    DEFAULT '',
                notes          TEXT    DEFAULT '',
                is_recurring   INTEGER DEFAULT 0,
                recurring_group TEXT   DEFAULT '',
                created_at     TEXT,
                updated_at     TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_exp_month ON expenses(month, year)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_exp_type ON expenses(expense_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_exp_status ON expenses(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_exp_annee ON expenses(annee_scolaire)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS expense_payments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_id     INTEGER NOT NULL,
                amount_paid    REAL    DEFAULT 0,
                payment_date   TEXT    NOT NULL,
                receipt_number TEXT    UNIQUE,
                notes          TEXT    DEFAULT '',
                created_at     TEXT,
                FOREIGN KEY (expense_id) REFERENCES expenses(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_exppay_exp ON expense_payments(expense_id)")

        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('last_expense_receipt_seq','0')")
        self.conn.commit()

    # ──────────────────────────────────────────────────────────────────
    # students
    # ──────────────────────────────────────────────────────────────────
    def _ensure_students_table(self, c):
        """
        Create the students table with the current schema, or upgrade it
        from an older version that had UNIQUE(matricule) alone and lacked
        `total_a_payer`.
        """
        # Does the table exist at all?
        exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='students'"
        ).fetchone()

        if not exists:
            # Fresh install – create target schema directly
            self._create_students_table(c)
            return

        # Table exists – check if it needs upgrading
        existing_sql = c.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='students'"
        ).fetchone()[0]

        col_names = [r[1] for r in c.execute("PRAGMA table_info(students)").fetchall()]
        needs_rebuild = "matricule TEXT UNIQUE NOT NULL" in existing_sql
        needs_total_a_payer    = "total_a_payer" not in col_names
        needs_inscription_amt  = "inscription_amount" not in col_names

        if needs_rebuild:
            # Rebuild with new UNIQUE(matricule, classe, annee_scolaire) constraint
            c.execute("ALTER TABLE students RENAME TO _students_old")
            self._create_students_table(c)

            old_cols  = [r[1] for r in c.execute("PRAGMA table_info(_students_old)").fetchall()]
            copy_cols = [col for col in old_cols if col != "id"]
            new_cols  = [r[1] for r in c.execute("PRAGMA table_info(students)").fetchall()]
            new_cols  = [col for col in new_cols if col != "id"]
            common    = [col for col in copy_cols if col in new_cols]

            c.execute(
                f"INSERT OR IGNORE INTO students ({','.join(common)}) "
                f"SELECT {','.join(common)} FROM _students_old"
            )
            c.execute("DROP TABLE _students_old")

        elif needs_total_a_payer or needs_inscription_amt:
            try:
                if needs_total_a_payer:
                    c.execute("ALTER TABLE students ADD COLUMN total_a_payer REAL DEFAULT 0")
                if needs_inscription_amt:
                    c.execute("ALTER TABLE students ADD COLUMN inscription_amount REAL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

        self.conn.commit()

    def _create_students_table(self, c):
        c.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                matricule       TEXT NOT NULL,
                eleve_nom       TEXT NOT NULL DEFAULT '',
                eleve_prenom    TEXT NOT NULL DEFAULT '',
                mere            TEXT,
                pere            TEXT,
                date_of_birth   TEXT,
                city_of_birth   TEXT,
                adresse         TEXT,
                pere_telephone  TEXT,
                mere_telephone  TEXT,
                classe          TEXT,
                inscription     TEXT,
                inscription_amount REAL DEFAULT 0,
                transport_yn    TEXT    DEFAULT 'N',
                transport       REAL    DEFAULT 0,
                mensualite      REAL    DEFAULT 0,
                total_a_payer   REAL    DEFAULT 0,
                note_date       TEXT,
                annee_scolaire  TEXT,
                date_creation   TEXT,
                statut          TEXT    DEFAULT 'Actif',
                UNIQUE (matricule, classe, annee_scolaire)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_students_annee ON students(annee_scolaire)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_students_classe ON students(classe)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_students_matricule ON students(matricule)")

    # ──────────────────────────────────────────────────────────────────
    # month_status
    # ──────────────────────────────────────────────────────────────────
    def _ensure_month_status_table(self, c):
        """
        Create month_status with student_id FK, or rebuild from the old
        version that used payment_student_id.
        """
        exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='month_status'"
        ).fetchone()

        if not exists:
            self._create_month_status_table(c)
            return

        col_names = [r[1] for r in c.execute("PRAGMA table_info(month_status)").fetchall()]
        if "student_id" not in col_names:
            # Old schema – rename, recreate, data migrated in Step 5
            c.execute("ALTER TABLE month_status RENAME TO _month_status_old")
            self._create_month_status_table(c)
        # else: already current, nothing to do

        self.conn.commit()

    def _create_month_status_table(self, c):
        c.execute("""
            CREATE TABLE IF NOT EXISTS month_status (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id     INTEGER NOT NULL,
                annee_scolaire TEXT    NOT NULL,
                month          TEXT    NOT NULL,
                status         TEXT    NOT NULL DEFAULT 'UNPAID',
                source         TEXT    NOT NULL DEFAULT 'import',
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE (student_id, annee_scolaire, month)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_month_status_student ON month_status(student_id)")

        # Additive upgrade: add `source` column if table exists but lacks it
    def _ensure_month_status_source_col(self, c):
        cols = [r[1] for r in c.execute("PRAGMA table_info(month_status)").fetchall()]
        if "source" not in cols:
            try:
                c.execute("ALTER TABLE month_status ADD COLUMN source TEXT NOT NULL DEFAULT 'import'")
                self.conn.commit()
            except Exception:
                pass

    # ──────────────────────────────────────────────────────────────────
    # payments
    # ──────────────────────────────────────────────────────────────────
    def _ensure_payments_table(self, c):
        exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payments'"
        ).fetchone()

        if not exists:
            self._create_payments_table(c)
            return

        col_names = [r[1] for r in c.execute("PRAGMA table_info(payments)").fetchall()]
        if "student_id" not in col_names:
            c.execute("ALTER TABLE payments RENAME TO _payments_old")
            self._create_payments_table(c)

        self.conn.commit()

    def _create_payments_table(self, c):
        c.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id     INTEGER NOT NULL,
                annee_scolaire TEXT    NOT NULL,
                payment_type   TEXT    NOT NULL,
                month          TEXT,
                amount         REAL    NOT NULL DEFAULT 0,
                payment_date   TEXT    NOT NULL,
                notes          TEXT,
                receipt_number TEXT    UNIQUE,
                date_creation  TEXT,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_student ON payments(student_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_annee ON payments(annee_scolaire)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_payments_month ON payments(month)")

    # ──────────────────────────────────────────────────────────────────
    # Step 5 – migrate legacy payment_students + old _*_old tables
    # ──────────────────────────────────────────────────────────────────
    def _migrate_payment_students_table(self, c):
        """
        Move data from legacy `payment_students` (if present) into `students`,
        then repoint `_month_status_old` and `_payments_old` to student_id.
        Cleans up all _*_old tables at the end.
        """
        # Build id-map: old payment_students.id → students.id
        id_map = {}

        legacy_exists = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='payment_students'"
        ).fetchone()

        if legacy_exists:
            rows = c.execute("SELECT * FROM payment_students").fetchall()
            if rows:
                col_names = [d[0] for d in c.description]
                for r in rows:
                    d = dict(zip(col_names, r))
                    mat    = str(d.get("matricule", ""))
                    cls    = str(d.get("classe", ""))
                    annee  = str(d.get("annee_scolaire", ""))

                    existing = c.execute(
                        "SELECT id FROM students WHERE matricule=? AND classe=? AND annee_scolaire=?",
                        (mat, cls, annee)
                    ).fetchone()

                    if existing:
                        new_id = existing[0]
                        c.execute(
                            "UPDATE students SET total_a_payer=? WHERE id=? AND (total_a_payer IS NULL OR total_a_payer=0)",
                            (d.get("total_a_payer") or 0, new_id)
                        )
                    else:
                        c.execute(
                            "INSERT OR IGNORE INTO students "
                            "(matricule, eleve_nom, eleve_prenom, classe, inscription, "
                            " transport, mensualite, total_a_payer, note_date, "
                            " annee_scolaire, date_creation, statut) "
                            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            (
                                mat,
                                d.get("nom") or "",
                                d.get("prenom") or "",
                                cls,
                                d.get("inscription") or "",
                                d.get("transport") or 0,
                                d.get("mensualite") or 0,
                                d.get("total_a_payer") or 0,
                                d.get("note_date") or "",
                                annee,
                                d.get("date_creation"),
                                "Actif",
                            )
                        )
                        new_id = c.lastrowid

                    id_map[d["id"]] = new_id

            c.execute("DROP TABLE payment_students")

        # Migrate _month_status_old → month_status
        old_ms = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_month_status_old'"
        ).fetchone()
        if old_ms:
            rows = c.execute("SELECT * FROM _month_status_old").fetchall()
            if rows:
                col_names = [d[0] for d in c.description]
                for r in rows:
                    d = dict(zip(col_names, r))
                    old_ps_id   = d.get("payment_student_id") or d.get("student_id")
                    new_sid     = id_map.get(old_ps_id, old_ps_id)
                    c.execute(
                        "INSERT OR IGNORE INTO month_status (student_id, annee_scolaire, month, status) "
                        "VALUES (?,?,?,?)",
                        (new_sid, d["annee_scolaire"], d["month"], d["status"])
                    )
            c.execute("DROP TABLE _month_status_old")

        # Migrate _payments_old → payments
        old_pay = c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='_payments_old'"
        ).fetchone()
        if old_pay:
            rows = c.execute("SELECT * FROM _payments_old").fetchall()
            if rows:
                col_names = [d[0] for d in c.description]
                for r in rows:
                    d = dict(zip(col_names, r))
                    old_ps_id = d.get("payment_student_id") or d.get("student_id")
                    new_sid   = id_map.get(old_ps_id, old_ps_id)
                    c.execute(
                        "INSERT OR IGNORE INTO payments "
                        "(student_id, annee_scolaire, payment_type, month, amount, "
                        " payment_date, notes, receipt_number, date_creation) "
                        "VALUES (?,?,?,?,?,?,?,?,?)",
                        (
                            new_sid,
                            d.get("annee_scolaire"),
                            d.get("payment_type"),
                            d.get("month"),
                            d.get("amount", 0),
                            d.get("payment_date", ""),
                            d.get("notes"),
                            d.get("receipt_number"),
                            d.get("date_creation"),
                        )
                    )
            c.execute("DROP TABLE _payments_old")

        self.conn.commit()

    # ──────────────────────────────────────────────────────────────────
    # Query helpers
    # ──────────────────────────────────────────────────────────────────
    def execute(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        self.conn.commit()
        return cursor

    def fetchall(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def fetchone(self, query, params=()):
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None

    # ──────────────────────────────────────────────────────────────────
    # Settings
    # ──────────────────────────────────────────────────────────────────
    def get_setting(self, key, default=None):
        row = self.fetchone("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )

    # ──────────────────────────────────────────────────────────────────
    # Backup
    # ──────────────────────────────────────────────────────────────────
    def backup_database(self):
        timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"school_backup_{timestamp}.db")
        self.conn.commit()
        shutil.copy2(DB_PATH, backup_path)
        return backup_path

    def close(self):
        self.conn.close()
