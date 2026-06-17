"""
Liste des Dépenses Page
========================
Full expense list with search, filters, sort, pagination,
add/edit/delete/pay actions and Excel export.
"""

import customtkinter as ctk
from tkinter import ttk, filedialog
import os

from utils.theme import COLORS, font_title, font_body, font_button
from models.expense import Expense, ALL_CATEGORIES, SCHOOL_MONTHS
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification, LoadingSpinner, ConfirmDialog

PAGE_SIZE = 20

TABLE_COLS = [
    ("expense_type", "Type",        80),
    ("category",     "Catégorie",  120),
    ("description",  "Description",160),
    ("amount",       "Montant",     90),
    ("month",        "Mois",        85),
    ("year",         "Année",       60),
    ("status",       "Statut",      90),
]


class ListeDepensesPage(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=("#F8FAFC", "#0F172A"), **kwargs)
        self.db          = DatabaseManager()
        self.school_year = self.db.get_setting("current_school_year", "2025/2026")

        self.search_var  = ctk.StringVar()
        self.type_var    = ctk.StringVar(value="Tous")
        self.cat_var     = ctk.StringVar(value="Toutes")
        self.status_var  = ctk.StringVar(value="Tous")
        self.month_var   = ctk.StringVar(value="Tous")

        self.all_rows    = []
        self.current_page = 1
        self.sort_col    = "month"
        self.sort_rev    = False

        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_pagination()
        self.refresh()

    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=25, pady=(20, 5))
        ctk.CTkLabel(h, text="📋 Liste des Dépenses", font=font_title()).pack(side="left")

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color=("white", COLORS["card_dark"]),
                             corner_radius=12, border_width=1,
                             border_color=("#E2E8F0", COLORS["border_dark"]))
        bar.pack(fill="x", padx=25, pady=10)

        r1 = ctk.CTkFrame(bar, fg_color="transparent")
        r1.pack(fill="x", padx=15, pady=(12, 6))

        self.search_entry = ctk.CTkEntry(
            r1, placeholder_text="🔍 Rechercher catégorie, description…",
            textvariable=self.search_var, width=260, font=font_body())
        self.search_entry.pack(side="left", padx=(0, 10))
        self.search_var.trace_add("write", lambda *_: self.refresh())

        def omenu(parent, values, var, width=110):
            m = ctk.CTkOptionMenu(parent, values=values, variable=var,
                                   command=lambda _: self.refresh(),
                                   fg_color=COLORS["primary"],
                                   button_color=COLORS["primary_hover"], width=width)
            m.pack(side="left", padx=5)
            return m

        omenu(r1, ["Tous", "Fixe", "Variable"], self.type_var, 100)
        self.cat_menu = omenu(r1, ["Toutes"] + ALL_CATEGORIES, self.cat_var, 160)
        omenu(r1, ["Tous", "Payé", "Non Payé"], self.status_var)
        omenu(r1, ["Tous"] + list(SCHOOL_MONTHS), self.month_var, 130)

        r2 = ctk.CTkFrame(bar, fg_color="transparent")
        r2.pack(fill="x", padx=15, pady=(0, 12))

        btns = [
            ("➕ Ajouter", COLORS["success"], "#16A34A", self._add),
            ("📥 Importer Excel", COLORS["secondary"], COLORS["primary_hover"], self._import),
            ("📤 Exporter Excel", "#0F766E", "#0D9488", self._export),
            ("🔄 Rafraîchir", "gray", "#475569", self.refresh),
        ]
        for text, fg, hov, cmd in btns:
            ctk.CTkButton(r2, text=text, font=font_button(), fg_color=fg,
                           hover_color=hov, command=cmd, width=140).pack(side="left", padx=5)

        self.count_label = ctk.CTkLabel(r2, text="", font=font_body())
        self.count_label.pack(side="right", padx=10)

    def _build_table(self):
        card = ctk.CTkFrame(self, fg_color=("white", COLORS["card_dark"]),
                             corner_radius=12, border_width=1,
                             border_color=("#E2E8F0", COLORS["border_dark"]))
        card.pack(fill="both", expand=True, padx=25, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Dep.Treeview", background="#FFFFFF", foreground="#1E293B",
                         rowheight=32, fieldbackground="#FFFFFF", borderwidth=0, font=("Segoe UI", 10))
        style.configure("Dep.Treeview.Heading", background="#7C3AED", foreground="white",
                         font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Dep.Treeview", background=[("selected", "#EDE9FE")],
                  foreground=[("selected", "#1E293B")])
        style.map("Dep.Treeview.Heading", background=[("active", "#6D28D9")])

        tf = ctk.CTkFrame(card, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=12, pady=12)

        cols = [c[0] for c in TABLE_COLS] + ["actions"]
        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style="Dep.Treeview", selectmode="browse")
        for key, lbl, w in TABLE_COLS:
            self.tree.heading(key, text=lbl, command=lambda k=key: self._sort(k))
            self.tree.column(key, width=w, anchor="center")
        self.tree.heading("actions", text="Actions")
        self.tree.column("actions", width=200, anchor="center")

        self.tree.tag_configure("paye",     foreground=COLORS["success"])
        self.tree.tag_configure("non_paye", foreground=COLORS["danger"])

        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", lambda e: self._on_double(e))
        self.tree.bind("<Button-1>", lambda e: self._on_click(e))

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
        t    = self.type_var.get()   if self.type_var.get()   != "Tous"    else None
        cat  = self.cat_var.get()    if self.cat_var.get()    != "Toutes"  else None
        sts  = self.status_var.get() if self.status_var.get() != "Tous"    else None
        mon  = self.month_var.get()  if self.month_var.get()  != "Tous"    else None
        srch = self.search_var.get().strip() or None

        self.all_rows = Expense.get_all(
            annee_scolaire=self.school_year,
            expense_type=t, category=cat, status=sts,
            month=mon, search=srch,
        )
        self._sort_rows()
        self.current_page = 1
        self._render_page()

    def _sort(self, col):
        self.sort_rev = not self.sort_rev if self.sort_col == col else False
        self.sort_col = col
        self._sort_rows(); self.current_page = 1; self._render_page()

    def _sort_rows(self):
        col = self.sort_col
        self.all_rows.sort(
            key=lambda r: (float(r.get(col) or 0) if col == "amount"
                           else str(r.get(col) or "").lower()),
            reverse=self.sort_rev,
        )

    def _render_page(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        total = len(self.all_rows)
        tp    = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page > tp: self.current_page = tp
        start = (self.current_page - 1) * PAGE_SIZE

        for row in self.all_rows[start:start+PAGE_SIZE]:
            tag = "paye" if row["status"] == "Payé" else "non_paye"
            self.tree.insert("", "end", iid=str(row["id"]), tags=(tag,), values=(
                row.get("expense_type", ""),
                row.get("category", ""),
                row.get("description", "") or "-",
                f"{row.get('amount', 0):,.0f} DH",
                row.get("month", ""),
                row.get("year", ""),
                row.get("status", ""),
                "✏️ Éditer   💳 Payer   🗑️ Supprimer",
            ))

        self.page_label.configure(text=f"Page {self.current_page} / {tp}")
        self.count_label.configure(text=f"Total: {total}")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < tp else "disabled")

    def _prev_page(self):
        if self.current_page > 1: self.current_page -= 1; self._render_page()
    def _next_page(self):
        tp = max((len(self.all_rows) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page < tp: self.current_page += 1; self._render_page()

    # ─────────────────────────────────────────────────────────────────
    def _on_double(self, event):
        item = self.tree.identify_row(event.y)
        if item: self._edit(int(item))

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        item   = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item: return
        col_index = int(column.replace("#", "")) - 1
        if col_index < len(TABLE_COLS): return
        bbox = self.tree.bbox(item, column)
        if not bbox: return
        rel_x = event.x - bbox[0]
        third = bbox[2] / 3
        eid   = int(item)
        if rel_x < third:         self._edit(eid)
        elif rel_x < 2 * third:   self._pay(eid)
        else:                      self._delete(eid)

    def _add(self):
        from views.expense_form_dialog import ExpenseFormDialog
        ExpenseFormDialog(self, on_save=self._on_change)

    def _edit(self, eid):
        from views.expense_form_dialog import ExpenseFormDialog
        ExpenseFormDialog(self, expense_id=eid, on_save=self._on_change)

    def _pay(self, eid):
        exp = Expense.get_by_id(eid)
        if exp and exp["status"] == "Payé":
            ToastNotification(self, "Cette dépense est déjà payée.", success=False); return
        from views.pay_expense_dialog import PayExpenseDialog
        PayExpenseDialog(self, eid, on_save=self._on_change)

    def _delete(self, eid):
        exp = Expense.get_by_id(eid)
        if not exp: return
        def do():
            Expense.delete(eid)
            ToastNotification(self, "Dépense supprimée.", success=True)
            self._on_change()
        ConfirmDialog(self, title="Supprimer la dépense",
                       message=f"Supprimer {exp['category']} – {exp.get('month','')} ?",
                       on_confirm=do)

    def _on_change(self):
        self.refresh()
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "pages") and "dashboard" in app.pages:
                app.pages["dashboard"].refresh()
        except Exception: pass

    def _import(self):
        path = filedialog.askopenfilename(title="Importer dépenses",
                                          filetypes=[("Excel", "*.xlsx *.xls")])
        if not path: return
        try:
            import pandas as pd
            df = pd.read_excel(path)
            created = 0
            for _, row in df.iterrows():
                try:
                    Expense.create({
                        "expense_type": str(row.get("Type", "Variable")).strip(),
                        "category":     str(row.get("Catégorie", "Divers")).strip(),
                        "description":  str(row.get("Description", "") or "").strip(),
                        "amount":       float(row.get("Montant", 0) or 0),
                        "month":        str(row.get("Mois", "") or "").strip(),
                        "year":         str(row.get("Année", "") or "").strip(),
                        "notes":        str(row.get("Notes", "") or "").strip(),
                        "annee_scolaire": self.school_year,
                    })
                    created += 1
                except Exception:
                    pass
            ToastNotification(self, f"{created} dépenses importées.", success=True)
            self._on_change()
        except Exception as e:
            ToastNotification(self, f"Erreur import: {e}", success=False)

    def _export(self):
        path = filedialog.asksaveasfilename(
            title="Exporter dépenses", defaultextension=".xlsx",
            filetypes=[("Excel", "*.xlsx")], initialfile="depenses.xlsx")
        if not path: return
        try:
            import pandas as pd
            rows = [{"Type": r["expense_type"], "Catégorie": r["category"],
                     "Description": r["description"], "Montant": r["amount"],
                     "Mois": r["month"], "Année": r["year"],
                     "Statut": r["status"], "Notes": r["notes"]}
                    for r in self.all_rows]
            pd.DataFrame(rows).to_excel(path, index=False)
            ToastNotification(self, f"Exporté: {os.path.basename(path)}", success=True)
        except Exception as e:
            ToastNotification(self, f"Erreur export: {e}", success=False)
