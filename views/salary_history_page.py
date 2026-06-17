"""
Salary History Page
====================
Full salary payment history across all employees with filters.
"""

import customtkinter as ctk
from tkinter import ttk

from utils.theme import COLORS, font_title, font_body, font_subtitle, font_button
from models.salary_payment import SalaryPayment, SCHOOL_MONTHS
from models.employee import Employee
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification


PAGE_SIZE = 20


class SalaryHistoryPage(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=("#F8FAFC", "#0F172A"), **kwargs)

        self.db          = DatabaseManager()
        self.school_year = self.db.get_setting("current_school_year", "2025/2026")

        self.emp_var    = ctk.StringVar(value="Tous")
        self.job_var    = ctk.StringVar(value="Tous")
        self.month_var  = ctk.StringVar(value="Tous")
        self.year_var   = ctk.StringVar(value="Tous")

        self.all_rows    = []
        self.current_page = 1

        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_pagination()
        self.refresh()

    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=25, pady=(20, 5))
        ctk.CTkLabel(h, text="🧾 Historique des Salaires", font=font_title()).pack(side="left")

    def _build_toolbar(self):
        bar = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=12,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        bar.pack(fill="x", padx=25, pady=10)
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=12)

        def omenu(parent, values, var, label, width=130):
            f = ctk.CTkFrame(parent, fg_color="transparent")
            f.pack(side="left", padx=6)
            ctk.CTkLabel(f, text=label, font=font_body()).pack(anchor="w")
            m = ctk.CTkOptionMenu(f, values=values, variable=var,
                                   command=lambda _: self._on_filter(),
                                   fg_color=COLORS["primary"],
                                   button_color=COLORS["primary_hover"], width=width)
            m.pack()
            return m

        self.emp_menu  = omenu(inner, ["Tous"], self.emp_var,  "Employé", 170)
        self.job_menu  = omenu(inner, ["Tous"], self.job_var,  "Poste")
        self.month_menu = omenu(inner, ["Tous"] + list(SCHOOL_MONTHS), self.month_var, "Mois")
        # Year options based on school year
        start = int(self.school_year.split("/")[0])
        years = ["Tous", str(start), str(start + 1)]
        self.year_menu = omenu(inner, years, self.year_var, "Année", 90)

        ctk.CTkButton(inner, text="🔄", width=36, fg_color=COLORS["secondary"],
                       hover_color=COLORS["primary_hover"],
                       command=self.refresh).pack(side="left", padx=6, pady=(18, 0))

        self.count_label = ctk.CTkLabel(inner, text="", font=font_body())
        self.count_label.pack(side="right", padx=10)

    def _build_table(self):
        card = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=12,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        card.pack(fill="both", expand=True, padx=25, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("SalH.Treeview", background="#FFFFFF", foreground="#1E293B",
                         rowheight=30, fieldbackground="#FFFFFF", borderwidth=0, font=("Segoe UI", 10))
        style.configure("SalH.Treeview.Heading", background="#2563EB", foreground="white",
                         font=("Segoe UI", 10, "bold"), relief="flat")

        tf = ctk.CTkFrame(card, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=12, pady=12)

        cols    = ["nom", "prenom", "job", "payment_month", "payment_year",
                   "amount_paid", "payment_date", "receipt_number", "notes"]
        headers = [("Nom", 110), ("Prénom", 100), ("Poste", 100),
                   ("Mois", 85), ("Année", 60), ("Montant", 90),
                   ("Date", 95), ("N° Reçu", 130), ("Notes", 140)]

        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style="SalH.Treeview", selectmode="browse")
        for col, (lbl, w) in zip(cols, headers):
            self.tree.heading(col, text=lbl)
            self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _build_pagination(self):
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.pack(fill="x", padx=25, pady=(0, 15))
        self.prev_btn = ctk.CTkButton(pf, text="◀ Précédent", width=110,
                                       fg_color=COLORS["secondary"],
                                       hover_color=COLORS["primary_hover"],
                                       command=self._prev_page)
        self.prev_btn.pack(side="left", padx=5)
        self.page_label = ctk.CTkLabel(pf, text="Page 1 / 1", font=font_body())
        self.page_label.pack(side="left", padx=15)
        self.next_btn = ctk.CTkButton(pf, text="Suivant ▶", width=110,
                                       fg_color=COLORS["secondary"],
                                       hover_color=COLORS["primary_hover"],
                                       command=self._next_page)
        self.next_btn.pack(side="left", padx=5)

    # ─────────────────────────────────────────────────────────────────
    def refresh(self):
        # Rebuild employee dropdown
        employees = Employee.get_all(statut="Actif")
        emp_opts  = ["Tous"] + [f"{e['nom']} {e['prenom']} ({e['cin']})" for e in employees]
        self._emp_map = {"Tous": None}
        for e in employees:
            key = f"{e['nom']} {e['prenom']} ({e['cin']})"
            self._emp_map[key] = e["id"]
        self.emp_menu.configure(values=emp_opts)
        if self.emp_var.get() not in emp_opts:
            self.emp_var.set("Tous")

        # Job filter
        jobs = ["Tous"] + Employee.get_distinct_jobs()
        self.job_menu.configure(values=jobs)
        if self.job_var.get() not in jobs:
            self.job_var.set("Tous")

        self._load_rows()

    def _on_filter(self):
        self.current_page = 1
        self._load_rows()

    def _load_rows(self):
        emp_key    = self.emp_var.get()
        emp_id     = self._emp_map.get(emp_key) if hasattr(self, "_emp_map") else None
        job        = self.job_var.get()  if self.job_var.get()  != "Tous" else None
        month      = self.month_var.get() if self.month_var.get() != "Tous" else None
        year       = self.year_var.get()  if self.year_var.get()  != "Tous" else None

        self.all_rows = SalaryPayment.get_history(
            employee_id=emp_id, job=job, month=month, year=year
        )
        self._render_page()

    def _render_page(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        total       = len(self.all_rows)
        total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page > total_pages:
            self.current_page = total_pages

        start = (self.current_page - 1) * PAGE_SIZE
        for row in self.all_rows[start: start + PAGE_SIZE]:
            self.tree.insert("", "end", values=(
                row.get("nom", ""), row.get("prenom", ""),
                row.get("job", ""), row.get("payment_month", ""),
                row.get("payment_year", ""),
                f"{row.get('amount_paid', 0):.0f} DH",
                row.get("payment_date", ""),
                row.get("receipt_number", ""),
                row.get("notes", "") or "",
            ))

        self.page_label.configure(text=f"Page {self.current_page} / {total_pages}")
        self.count_label.configure(text=f"{total} paiement(s)")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        tp = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        self.next_btn.configure(state="normal" if self.current_page < tp else "disabled")

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1; self._render_page()

    def _next_page(self):
        tp = max((len(self.all_rows) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page < tp:
            self.current_page += 1; self._render_page()
