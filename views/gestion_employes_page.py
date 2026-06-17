"""
Gestion des Employés Page
==========================
Professional table view of all employees — same UX as Gestion des Élèves.
Search / filter / sort / paginate / add / edit / delete / import / export.
"""

import customtkinter as ctk
from tkinter import ttk, filedialog
import os

from utils.theme import COLORS, font_title, font_body, font_subtitle, font_button
from models.employee import Employee
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification, LoadingSpinner, ConfirmDialog


PAGE_SIZE = 15

TABLE_COLUMNS = [
    ("cin",    "CIN",     90),
    ("nom",    "Nom",    120),
    ("prenom", "Prénom", 120),
    ("job",    "Poste",  110),
    ("classe", "Classes", 140),
    ("salary", "Salaire", 90),
]


class GestionEmployesPage(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=("#F8FAFC", "#0F172A"), **kwargs)

        self.db          = DatabaseManager()
        self.search_var  = ctk.StringVar()
        self.job_var     = ctk.StringVar(value="Tous")
        self.school_year = self.db.get_setting("current_school_year", "2025/2026")

        self.all_rows    = []
        self.current_page = 1
        self.sort_column  = "nom"
        self.sort_reverse = False

        self._build_header()
        self._build_toolbar()
        self._build_table()
        self._build_pagination()
        self.refresh()

    # ──────────────────────────────────────────────────────────────────
    def _build_header(self):
        h = ctk.CTkFrame(self, fg_color="transparent")
        h.pack(fill="x", padx=25, pady=(20, 5))
        ctk.CTkLabel(h, text="👥 Gestion des Employés", font=font_title()).pack(side="left")

    def _build_toolbar(self):
        toolbar = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=12,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        toolbar.pack(fill="x", padx=25, pady=10)

        r1 = ctk.CTkFrame(toolbar, fg_color="transparent")
        r1.pack(fill="x", padx=15, pady=(12, 6))

        self.search_entry = ctk.CTkEntry(
            r1, placeholder_text="🔍 Rechercher CIN, Nom, Prénom, Poste…",
            textvariable=self.search_var, width=300, font=font_body(),
        )
        self.search_entry.pack(side="left", padx=(0, 12))
        self.search_var.trace_add("write", lambda *_: self._on_filter())

        self.job_menu = ctk.CTkOptionMenu(
            r1, values=["Tous"], variable=self.job_var,
            command=lambda _: self._on_filter(), width=130,
            fg_color=COLORS["primary"], button_color=COLORS["primary_hover"],
        )
        self.job_menu.pack(side="left", padx=6)

        r2 = ctk.CTkFrame(toolbar, fg_color="transparent")
        r2.pack(fill="x", padx=15, pady=(0, 12))

        ctk.CTkButton(r2, text="➕ Ajouter", font=font_button(),
                       fg_color=COLORS["success"], hover_color="#16A34A",
                       command=self._add_employee, width=130).pack(side="left", padx=(0, 8))

        ctk.CTkButton(r2, text="📥 Importer Excel", font=font_button(),
                       fg_color=COLORS["secondary"], hover_color=COLORS["primary_hover"],
                       command=self._import_excel, width=150).pack(side="left", padx=8)

        ctk.CTkButton(r2, text="📤 Exporter Excel", font=font_button(),
                       fg_color="#0F766E", hover_color="#0D9488",
                       command=self._export_excel, width=150).pack(side="left", padx=8)

        ctk.CTkButton(r2, text="🔄 Rafraîchir", font=font_button(),
                       fg_color="gray", hover_color="#475569",
                       command=self.refresh, width=120).pack(side="left", padx=8)

        ctk.CTkButton(r2, text="💰 Payer Salaire", font=font_button(),
                       fg_color=COLORS["warning"], hover_color="#D97706",
                       command=self._pay_salary_shortcut, width=140).pack(side="left", padx=8)

        self.count_label = ctk.CTkLabel(r2, text="", font=font_body())
        self.count_label.pack(side="right", padx=10)

    def _build_table(self):
        card = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=12,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        card.pack(fill="both", expand=True, padx=25, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Emp.Treeview", background="#FFFFFF", foreground="#1E293B",
                         rowheight=32, fieldbackground="#FFFFFF", borderwidth=0, font=("Segoe UI", 10))
        style.configure("Emp.Treeview.Heading", background="#2563EB", foreground="white",
                         font=("Segoe UI", 10, "bold"), relief="flat")
        style.map("Emp.Treeview.Heading", background=[("active", "#1D4ED8")])
        style.map("Emp.Treeview", background=[("selected", "#DBEAFE")], foreground=[("selected", "#1E293B")])

        tf = ctk.CTkFrame(card, fg_color="transparent")
        tf.pack(fill="both", expand=True, padx=12, pady=12)

        cols = [c[0] for c in TABLE_COLUMNS] + ["actions"]
        self.tree = ttk.Treeview(tf, columns=cols, show="headings",
                                  style="Emp.Treeview", selectmode="browse")
        for key, label, width in TABLE_COLUMNS:
            self.tree.heading(key, text=label, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=width, anchor="center")
        self.tree.heading("actions", text="Actions")
        self.tree.column("actions", width=180, anchor="center")

        vsb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-1>",  self._on_click)

    def _build_pagination(self):
        pf = ctk.CTkFrame(self, fg_color="transparent")
        pf.pack(fill="x", padx=25, pady=(0, 15))

        self.prev_btn = ctk.CTkButton(pf, text="◀ Précédent", width=110,
                                       fg_color=COLORS["secondary"], hover_color=COLORS["primary_hover"],
                                       command=self._prev_page)
        self.prev_btn.pack(side="left", padx=5)
        self.page_label = ctk.CTkLabel(pf, text="Page 1 / 1", font=font_body())
        self.page_label.pack(side="left", padx=15)
        self.next_btn = ctk.CTkButton(pf, text="Suivant ▶", width=110,
                                       fg_color=COLORS["secondary"], hover_color=COLORS["primary_hover"],
                                       command=self._next_page)
        self.next_btn.pack(side="left", padx=5)

    # ──────────────────────────────────────────────────────────────────
    # Data
    # ──────────────────────────────────────────────────────────────────
    def refresh(self):
        jobs = ["Tous"] + Employee.get_distinct_jobs()
        self.job_menu.configure(values=jobs)
        if self.job_var.get() not in jobs:
            self.job_var.set("Tous")

        job    = self.job_var.get() if self.job_var.get() != "Tous" else None
        search = self.search_var.get().strip() or None
        self.all_rows = Employee.get_all(job=job, search=search)
        self._sort_rows()
        self.current_page = 1
        self._render_page()

    def _on_filter(self):
        self.refresh()

    def _sort_by(self, column):
        self.sort_reverse = not self.sort_reverse if self.sort_column == column else False
        self.sort_column  = column
        self._sort_rows()
        self.current_page = 1
        self._render_page()

    def _sort_rows(self):
        col = self.sort_column
        self.all_rows.sort(
            key=lambda r: (float(r.get(col) or 0) if col == "salary"
                           else str(r.get(col) or "").lower()),
            reverse=self.sort_reverse,
        )

    def _render_page(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        total       = len(self.all_rows)
        total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page > total_pages:
            self.current_page = total_pages

        start = (self.current_page - 1) * PAGE_SIZE
        for row in self.all_rows[start: start + PAGE_SIZE]:
            self.tree.insert("", "end", iid=str(row["id"]), values=(
                row.get("cin", ""),
                row.get("nom", ""),
                row.get("prenom", "") or "-",
                row.get("job", "") or "-",
                row.get("classe", "") or "-",
                f"{row.get('salary', 0):.0f} DH",
                "✏️ Éditer   💰 Salaire   🗑️",
            ))

        self.page_label.configure(text=f"Page {self.current_page} / {total_pages}")
        self.count_label.configure(text=f"Total: {total} employé(s)")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages else "disabled")

    def _prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1; self._render_page()

    def _next_page(self):
        tp = max((len(self.all_rows) + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        if self.current_page < tp:
            self.current_page += 1; self._render_page()

    # ──────────────────────────────────────────────────────────────────
    # Interactions
    # ──────────────────────────────────────────────────────────────────
    def _on_double_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self._edit_employee(int(item))

    def _on_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region != "cell": return
        item   = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item: return

        col_index = int(column.replace("#", "")) - 1
        col_count = len(TABLE_COLUMNS)
        if col_index < col_count: return    # not in actions column

        bbox = self.tree.bbox(item, column)
        if not bbox: return
        rel_x     = event.x - bbox[0]
        third     = bbox[2] / 3
        emp_id    = int(item)

        if rel_x < third:
            self._edit_employee(emp_id)
        elif rel_x < 2 * third:
            self._open_salary_dialog(emp_id)
        else:
            self._delete_employee(emp_id)

    def _add_employee(self):
        from views.employee_form_dialog import EmployeeFormDialog
        EmployeeFormDialog(self, on_save=self._on_change)

    def _edit_employee(self, emp_id):
        from views.employee_form_dialog import EmployeeFormDialog
        EmployeeFormDialog(self, employee_id=emp_id, on_save=self._on_change)

    def _delete_employee(self, emp_id):
        emp = Employee.get_by_id(emp_id)
        if not emp: return

        def do_delete():
            Employee.delete(emp_id)
            ToastNotification(self, f"{emp['nom']} supprimé.", success=True)
            self._on_change()

        ConfirmDialog(
            self, title="Supprimer l'employé",
            message=f"Voulez-vous supprimer {emp['nom']} {emp.get('prenom','')} ?",
            on_confirm=do_delete,
        )

    def _open_salary_dialog(self, emp_id):
        from views.salary_payment_dialog import SalaryPaymentDialog
        SalaryPaymentDialog(self, emp_id, self.school_year, on_save=self._on_change)

    def _pay_salary_shortcut(self):
        sel = self.tree.selection()
        if sel:
            self._open_salary_dialog(int(sel[0]))
        else:
            ToastNotification(self, "Sélectionnez un employé dans le tableau.", success=True)

    def _on_change(self):
        self.refresh()
        self._refresh_dashboard()

    def _refresh_dashboard(self):
        try:
            app = self.winfo_toplevel()
            if hasattr(app, "pages") and "dashboard" in app.pages:
                app.pages["dashboard"].refresh()
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # Import / Export
    # ──────────────────────────────────────────────────────────────────
    def _import_excel(self):
        path = filedialog.askopenfilename(
            title="Importer les employés (Excel)",
            filetypes=[("Fichiers Excel", "*.xlsx *.xls")],
        )
        if not path: return
        spinner = LoadingSpinner(self, "Importation en cours…")
        self.update_idletasks()
        try:
            from utils.employee_excel_handler import import_employees_excel
            summary = import_employees_excel(path)
            spinner.close()
            msg = (f"Import terminé : {summary['created']} créés, "
                   f"{summary['updated']} mis à jour.")
            if summary["errors"]:
                msg += f" {len(summary['errors'])} erreur(s)."
            ToastNotification(self, msg, success=len(summary["errors"]) == 0)
            self._on_change()
        except Exception as e:
            spinner.close()
            ToastNotification(self, f"Erreur : {e}", success=False)

    def _export_excel(self):
        path = filedialog.asksaveasfilename(
            title="Exporter les employés",
            defaultextension=".xlsx",
            filetypes=[("Fichiers Excel", "*.xlsx")],
            initialfile="export_employes.xlsx",
        )
        if not path: return
        try:
            from utils.employee_excel_handler import export_employees_excel
            export_employees_excel(self.all_rows, path)
            ToastNotification(self, f"Exporté : {os.path.basename(path)}", success=True)
        except Exception as e:
            ToastNotification(self, f"Erreur export : {e}", success=False)
