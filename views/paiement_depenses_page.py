"""
Paiement Dépenses Page
========================
Shows unpaid expenses with month-status chips per category group,
payment history, and quick-pay buttons.
"""

import customtkinter as ctk
from tkinter import ttk

from utils.theme import COLORS, font_title, font_body, font_subtitle, font_button
from models.expense import Expense, ExpensePayment, SCHOOL_MONTHS, ALL_CATEGORIES
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification, ConfirmDialog

PAGE_SIZE = 20

TABLE_COLS = [
    ("category",    "Catégorie",   130),
    ("description", "Description", 170),
    ("amount",      "Montant",      90),
    ("month",       "Mois",         90),
    ("year",        "Année",        60),
    ("expense_type","Type",         80),
    ("status",      "Statut",       90),
]


class PaiementDepensesPage(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=("#F8FAFC", "#0F172A"), **kwargs)

        self.db          = DatabaseManager()
        self.school_year = self.db.get_setting("current_school_year", "2025/2026")

        self.search_var = ctk.StringVar()
        self.cat_var    = ctk.StringVar(value="Toutes")
        self.month_var  = ctk.StringVar(value="Tous")
        self.type_var   = ctk.StringVar(value="Tous")

        self.all_rows    = []
        self.current_page = 1
        self.active_tab  = "unpaid"   # "unpaid" | "history"

        self._build_header()
        self._build_tabs()
        self._build_summary_bar()
        self._build_toolbar()
        self._build_table()
        self._build_pagination()
        self.refresh()

    # ─────────────────────────────────────────────────────────────────
    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=25, pady=(20, 5))
        ctk.CTkLabel(h, text="💳 Paiement des Dépenses", font=font_title()).pack(side="left")
        ctk.CTkButton(
            h, text="➕ Ajouter Dépense", font=font_button(),
            fg_color=COLORS["success"], hover_color="#16A34A",
            command=self._add_expense, width=160,
        ).pack(side="right")

    def _build_tabs(self):
        tab_frame = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=10,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        tab_frame.pack(fill="x", padx=25, pady=(0, 8))
        inner = ctk.CTkFrame(tab_frame, fg_color="transparent")
        inner.pack(padx=10, pady=8, anchor="w")

        self.tab_unpaid = ctk.CTkButton(
            inner, text="❌ Dépenses Non Payées", font=font_button(), width=190,
            fg_color=COLORS["danger"], hover_color="#B91C1C",
            command=lambda: self._switch_tab("unpaid"),
        )
        self.tab_unpaid.pack(side="left", padx=5)

        self.tab_history = ctk.CTkButton(
            inner, text="📋 Historique Paiements", font=font_button(), width=190,
            fg_color="gray", hover_color="#475569",
            command=lambda: self._switch_tab("history"),
        )
        self.tab_history.pack(side="left", padx=5)

    def _switch_tab(self, tab):
        self.active_tab = tab
        self.current_page = 1
        if tab == "unpaid":
            self.tab_unpaid.configure(fg_color=COLORS["danger"])
            self.tab_history.configure(fg_color="gray")
        else:
            self.tab_unpaid.configure(fg_color="gray")
            self.tab_history.configure(fg_color=COLORS["primary"])
        self.refresh()

    def _build_summary_bar(self):
        """KPI strip: total unpaid count + amount."""
        self.summary_frame = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=10,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        self.summary_frame.pack(fill="x", padx=25, pady=(0, 8))
        inner = ctk.CTkFrame(self.summary_frame, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)
        for i in range(3):
            inner.grid_columnconfigure(i, weight=1)

        self.kpi_unpaid_count  = self._kpi_widget(inner, "Dépenses Non Payées", "0", COLORS["danger"], 0)
        self.kpi_unpaid_amount = self._kpi_widget(inner, "Montant Restant (DH)", "0", COLORS["warning"], 1)
        self.kpi_paid_amount   = self._kpi_widget(inner, "Total Payé (DH)", "0", COLORS["success"], 2)

    def _kpi_widget(self, parent, title, value, color, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, sticky="ew", padx=10)
        vl = ctk.CTkLabel(f, text=value, font=ctk.CTkFont(size=22, weight="bold"),
                           text_color=color)
        vl.pack(anchor="w")
        ctk.CTkLabel(f, text=title, font=font_body(),
                     text_color=("#64748B", "#94A3B8")).pack(anchor="w")
        return vl

    def _build_toolbar(self):
        bar = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=10,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        bar.pack(fill="x", padx=25, pady=(0, 8))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=10)

        self.search_entry = ctk.CTkEntry(
            inner, placeholder_text="🔍 Rechercher…",
            textvariable=self.search_var, width=220, font=font_body(),
        )
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_var.trace_add("write", lambda *_: self.refresh())

        def omenu(values, var, width=120):
            m = ctk.CTkOptionMenu(
                inner, values=values, variable=var,
                command=lambda _: self.refresh(),
                fg_color=COLORS["primary"], button_color=COLORS["primary_hover"],
                width=width,
            )
            m.pack(side="left", padx=5)
            return m

        self.cat_menu   = omenu(["Toutes"] + ALL_CATEGORIES, self.cat_var, 160)
        self.month_menu = omenu(["Tous"] + list(SCHOOL_MONTHS), self.month_var, 130)
        omenu(["Tous", "Fixe", "Variable"], self.type_var, 100)

        ctk.CTkButton(
            inner, text="🔄", width=36,
            fg_color=COLORS["secondary"], hover_color=COLORS["primary_hover"],
            command=self.refresh,
        ).pack(side="left", padx=5)

        self.count_label = ctk.CTkLabel(inner, text="", font=font_body())
        self.count_label.pack(side="right", padx=10)

    def _build_table(self):
        card = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=12,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        card.pack(fill="both", expand=True, padx=25, pady=5)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("DepPay.Treeview", background="#FFFFFF", foreground="#1E293B",
                         rowheight=32, fieldbackground="#FFFFFF", borderwidth=0, font=("Segoe UI", 10))
        style.configure("DepPay.Treeview.Heading", background="#7C3AED", foreground="white",
                         font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("DepPay.Treeview", background=[("selected", "#EDE9FE")],
                  foreground=[("selected", "#1E293B")])

        tf = ctk.CTkFrame(card, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=12, pady=12)

        # Columns differ between tabs
        self._build_tree(tf)

    def _build_tree(self, parent):
        for w in parent.winfo_children():
            w.destroy()

        if self.active_tab == "unpaid":
            cols = [c[0] for c in TABLE_COLS] + ["actions"]
            self.tree = ttk.Treeview(parent, columns=cols, show="headings",
                                      style="DepPay.Treeview", selectmode="browse")
            for key, lbl, w in TABLE_COLS:
                self.tree.heading(key, text=lbl)
                self.tree.column(key, width=w, anchor="center")
            self.tree.heading("actions", text="Actions")
            self.tree.column("actions", width=130, anchor="center")
            self.tree.tag_configure("non_paye", foreground=COLORS["danger"])
        else:
            cols = ["category", "description", "month", "year", "amount_paid",
                    "payment_date", "receipt_number", "notes"]
            headers = [("Catégorie", 120), ("Description", 160), ("Mois", 85),
                       ("Année", 60), ("Montant", 90), ("Date", 95),
                       ("N° Reçu", 130), ("Notes", 140)]
            self.tree = ttk.Treeview(parent, columns=cols, show="headings",
                                      style="DepPay.Treeview", selectmode="browse")
            for col, (lbl, w) in zip(cols, headers):
                self.tree.heading(col, text=lbl)
                self.tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(parent, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        if self.active_tab == "unpaid":
            self.tree.bind("<Button-1>", self._on_click)

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
        # Update summary KPIs
        unpaid_count  = Expense.count_unpaid(annee_scolaire=self.school_year)
        unpaid_amount = Expense.total_expenses(annee_scolaire=self.school_year) - \
                        Expense.total_paid_expenses(annee_scolaire=self.school_year)
        paid_amount   = Expense.total_paid_expenses(annee_scolaire=self.school_year)

        self.kpi_unpaid_count.configure(text=str(unpaid_count))
        self.kpi_unpaid_amount.configure(text=f"{unpaid_amount:,.0f}")
        self.kpi_paid_amount.configure(text=f"{paid_amount:,.0f}")

        # Filters
        cat   = self.cat_var.get()   if self.cat_var.get()   != "Toutes" else None
        mon   = self.month_var.get() if self.month_var.get() != "Tous"   else None
        etype = self.type_var.get()  if self.type_var.get()  != "Tous"   else None
        srch  = self.search_var.get().strip() or None

        if self.active_tab == "unpaid":
            self.all_rows = Expense.get_all(
                annee_scolaire=self.school_year, status="Non Payé",
                category=cat, month=mon, expense_type=etype, search=srch,
            )
        else:
            self.all_rows = ExpensePayment.get_history(
                month=mon if mon else None, category=cat,
            )

        # Rebuild tree columns for current tab
        tf = None
        for w in self.winfo_children():
            if isinstance(w, ctk.CTkFrame) and hasattr(w, "winfo_children"):
                for c in w.winfo_children():
                    if isinstance(c, ctk.CTkFrame) and hasattr(c, "winfo_children"):
                        for cc in c.winfo_children():
                            if isinstance(cc, ttk.Treeview):
                                tf = c; break
        # Simpler: just clear and re-populate the existing tree
        if hasattr(self, "tree"):
            try:
                parent = self.tree.master
                self._build_tree(parent)
            except Exception:
                pass

        self.current_page = 1
        self._render_page()

    def _render_page(self):
        if not hasattr(self, "tree"): return
        for item in self.tree.get_children():
            self.tree.delete(item)

        total = len(self.all_rows)
        tp    = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page > tp: self.current_page = tp
        start = (self.current_page - 1) * PAGE_SIZE

        if self.active_tab == "unpaid":
            for row in self.all_rows[start:start + PAGE_SIZE]:
                self.tree.insert("", "end", iid=str(row["id"]),
                                  tags=("non_paye",), values=(
                    row.get("expense_type", ""),
                    row.get("category", ""),
                    row.get("description", "") or "-",
                    f"{row.get('amount', 0):,.0f} DH",
                    row.get("month", ""),
                    row.get("year", ""),
                    row.get("status", ""),
                    "💳 Payer   🗑️",
                ))
        else:
            for row in self.all_rows[start:start + PAGE_SIZE]:
                self.tree.insert("", "end", values=(
                    row.get("category", ""),
                    row.get("description", "") or "-",
                    row.get("month", ""),
                    row.get("year", ""),
                    f"{row.get('amount_paid', 0):,.0f} DH",
                    row.get("payment_date", ""),
                    row.get("receipt_number", ""),
                    row.get("notes", "") or "",
                ))

        self.page_label.configure(text=f"Page {self.current_page} / {tp}")
        self.count_label.configure(text=f"{total} enregistrement(s)")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < tp else "disabled")

    def _prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self._render_page()

    def _next_page(self):
        tp = max((len(self.all_rows) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page < tp: self.current_page += 1; self._render_page()

    # ─────────────────────────────────────────────────────────────────
    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        item   = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item: return
        col_idx = int(column.replace("#", "")) - 1
        if col_idx < len(TABLE_COLS): return
        bbox = self.tree.bbox(item, column)
        if not bbox: return
        rel_x = event.x - bbox[0]
        eid   = int(item)
        if rel_x < bbox[2] / 2:
            self._pay(eid)
        else:
            self._delete(eid)

    def _pay(self, eid):
        from views.pay_expense_dialog import PayExpenseDialog
        PayExpenseDialog(self, eid, on_save=self._on_change)

    def _delete(self, eid):
        exp = Expense.get_by_id(eid)
        if not exp: return
        def do():
            Expense.delete(eid)
            ToastNotification(self, "Dépense supprimée.", success=True)
            self._on_change()
        ConfirmDialog(self, title="Supprimer",
                       message=f"Supprimer {exp['category']} – {exp.get('month','')} ?",
                       on_confirm=do)

    def _add_expense(self):
        from views.expense_form_dialog import ExpenseFormDialog
        ExpenseFormDialog(self, on_save=self._on_change)

    def _on_change(self):
        self.refresh()
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "pages") and "dashboard" in app.pages:
                app.pages["dashboard"].refresh()
        except Exception:
            pass
