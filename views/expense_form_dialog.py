"""
Expense Form Dialog
====================
Add / Edit expense with recurring-expense generator for Fixe type.
"""

import customtkinter as ctk
from utils.theme import COLORS, font_title, font_subtitle, font_body, font_button
from models.expense import (Expense, FIXED_CATEGORIES, VARIABLE_CATEGORIES,
                             ALL_CATEGORIES, SCHOOL_MONTHS)
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification


class ExpenseFormDialog(ctk.CTkToplevel):

    def __init__(self, master, expense_id=None, on_save=None):
        super().__init__(master)
        self.expense_id = expense_id
        self.on_save    = on_save
        self.is_edit    = expense_id is not None
        self.db         = DatabaseManager()

        self.type_var    = ctk.StringVar(value="Fixe")
        self.recur_var   = ctk.BooleanVar(value=False)
        self._month_vars = {}

        self.title("Modifier dépense" if self.is_edit else "Ajouter dépense")
        self.geometry("640x660")
        self.minsize(560, 560)
        self.grab_set()
        self.transient(master)

        self._existing = Expense.get_by_id(expense_id) if self.is_edit else {}
        self._build_ui()
        self._center(master)

    def _center(self, m):
        self.update_idletasks()
        x = m.winfo_x() + m.winfo_width()//2 - self.winfo_width()//2
        y = m.winfo_y() + m.winfo_height()//2 - self.winfo_height()//2
        self.geometry(f"+{x}+{y}")

    def _card(self, parent):
        return ctk.CTkFrame(parent, fg_color=("white", COLORS["card_dark"]),
                             corner_radius=12, border_width=1,
                             border_color=("#E2E8F0", COLORS["border_dark"]))

    def _build_ui(self):
        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0, height=62)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text="✏️ Dépense" if self.is_edit else "➕ Nouvelle Dépense",
                      font=font_title(), text_color="white").pack(side="left", padx=18, pady=14)
        ctk.CTkButton(hdr, text="✕", width=36, height=36, corner_radius=8,
                       fg_color=COLORS["danger"], hover_color="#B91C1C",
                       text_color="white", command=self.destroy).pack(side="right", padx=12)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=10)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        e = self._existing
        school_year = self.db.get_setting("current_school_year", "2025/2026")
        start_yr    = int(school_year.split("/")[0])
        end_yr      = int(school_year.split("/")[1])

        # Expense Type
        f0 = ctk.CTkFrame(scroll, fg_color="transparent")
        f0.grid(row=0, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f0, text="Type *", font=font_body(), anchor="w").pack(anchor="w")
        self.type_menu = ctk.CTkOptionMenu(
            f0, values=["Fixe", "Variable"], variable=self.type_var,
            fg_color=COLORS["primary"], button_color=COLORS["primary_hover"],
            command=self._on_type_change,
        )
        self.type_menu.set(e.get("expense_type", "Fixe"))
        self.type_menu.pack(fill="x", pady=(2, 0))

        # Category
        f1 = ctk.CTkFrame(scroll, fg_color="transparent")
        f1.grid(row=0, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f1, text="Catégorie *", font=font_body(), anchor="w").pack(anchor="w")
        self.cat_menu = ctk.CTkOptionMenu(
            f1, values=FIXED_CATEGORIES if self.type_var.get() == "Fixe" else VARIABLE_CATEGORIES,
            fg_color=COLORS["primary"], button_color=COLORS["primary_hover"],
        )
        self.cat_menu.set(e.get("category", "") or FIXED_CATEGORIES[0])
        self.cat_menu.pack(fill="x", pady=(2, 0))

        # Description
        self.desc_entry = self._entry(scroll, "Description", e.get("description", ""), 1, 0, 2)

        # Amount
        self.amt_entry  = self._entry(scroll, "Montant (DH) *", str(e.get("amount", "") or ""), 2, 0)

        # Month
        f_mon = ctk.CTkFrame(scroll, fg_color="transparent")
        f_mon.grid(row=2, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f_mon, text="Mois", font=font_body(), anchor="w").pack(anchor="w")
        self.month_menu = ctk.CTkOptionMenu(
            f_mon, values=list(SCHOOL_MONTHS),
            fg_color=COLORS["primary"], button_color=COLORS["primary_hover"],
        )
        self.month_menu.set(e.get("month", SCHOOL_MONTHS[0]))
        self.month_menu.pack(fill="x", pady=(2, 0))

        # Year
        year_vals = [str(start_yr), str(end_yr)]
        self.yr_entry = self._combo(scroll, "Année", e.get("year", str(start_yr)), year_vals, 3, 0)

        # Annee scolaire (hidden/auto)
        self._annee_scolaire = school_year

        # Notes
        self.notes_entry = self._entry(scroll, "Notes", e.get("notes", ""), 3, 1)

        # Recurring panel (Fixe only)
        self.recur_panel = self._card(scroll)
        self.recur_panel.grid(row=4, column=0, columnspan=2, sticky="ew", padx=6, pady=10)
        ctk.CTkLabel(self.recur_panel, text="🔁 Dépense récurrente (Fixe)",
                      font=font_subtitle()).pack(anchor="w", padx=14, pady=(10, 4))
        ctk.CTkCheckBox(self.recur_panel, text="Générer automatiquement pour tous les mois",
                         variable=self.recur_var, font=font_body(),
                         command=self._on_recur_toggle).pack(anchor="w", padx=14, pady=(0, 6))

        self.month_checks_frame = ctk.CTkFrame(self.recur_panel, fg_color="transparent")
        self.month_checks_frame.pack(fill="x", padx=14, pady=(0, 10))
        self._build_month_checkboxes()

        # Save button
        ctk.CTkButton(scroll, text="💾 Enregistrer", font=font_button(), height=44,
                       fg_color=COLORS["success"], hover_color="#16A34A",
                       command=self._save).grid(row=5, column=0, columnspan=2,
                                                sticky="ew", padx=6, pady=16)
        self._on_type_change(self.type_var.get())

    def _entry(self, parent, label, value, row, col, colspan=1):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f, text=label, font=font_body(), anchor="w").pack(anchor="w")
        e = ctk.CTkEntry(f, font=font_body())
        e.insert(0, str(value) if value is not None else "")
        e.pack(fill="x", pady=(2, 0))
        return e

    def _combo(self, parent, label, value, values, row, col):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=col, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f, text=label, font=font_body(), anchor="w").pack(anchor="w")
        m = ctk.CTkOptionMenu(f, values=values, fg_color=COLORS["primary"],
                               button_color=COLORS["primary_hover"])
        m.set(value)
        m.pack(fill="x", pady=(2, 0))
        return m

    def _build_month_checkboxes(self):
        for w in self.month_checks_frame.winfo_children():
            w.destroy()
        self._month_vars.clear()
        for i, month in enumerate(SCHOOL_MONTHS):
            var = ctk.BooleanVar(value=True)
            chk = ctk.CTkCheckBox(self.month_checks_frame, text=month, variable=var,
                                   font=font_body(), checkbox_width=18, checkbox_height=18)
            chk.grid(row=i//5, column=i%5, sticky="w", padx=6, pady=2)
            self._month_vars[month] = var
        self.month_checks_frame.grid_columnconfigure(tuple(range(5)), weight=1)

    def _on_type_change(self, value):
        cats = FIXED_CATEGORIES if value == "Fixe" else VARIABLE_CATEGORIES
        self.cat_menu.configure(values=cats)
        self.cat_menu.set(cats[0])
        # Show recurring panel only for Fixe
        if value == "Fixe" and not self.is_edit:
            self.recur_panel.grid()
        else:
            self.recur_panel.grid_remove()

    def _on_recur_toggle(self):
        if self.recur_var.get():
            self.month_checks_frame.pack(fill="x", padx=14, pady=(0, 10))
        else:
            self.month_checks_frame.pack_forget()

    def _save(self):
        category = self.cat_menu.get()
        desc     = self.desc_entry.get().strip()
        amt_str  = self.amt_entry.get().strip()
        notes    = self.notes_entry.get().strip()
        month    = self.month_menu.get()
        year     = self.yr_entry.get() if hasattr(self.yr_entry, "get") else str(self.yr_entry)

        if not amt_str:
            ToastNotification(self, "Le montant est obligatoire.", success=False); return
        try:
            amount = float(amt_str)
        except ValueError:
            ToastNotification(self, "Le montant doit être un nombre.", success=False); return

        exp_type = self.type_var.get()

        if self.is_edit:
            Expense.update(self.expense_id, {
                "expense_type": exp_type, "category": category,
                "description": desc, "amount": amount,
                "month": month, "year": year,
                "annee_scolaire": self._annee_scolaire, "notes": notes,
            })
            ToastNotification(self, "Dépense modifiée.", success=True)
        else:
            if self.recur_var.get() and exp_type == "Fixe":
                selected_months = [m for m, v in self._month_vars.items() if v.get()]
                if not selected_months:
                    ToastNotification(self, "Sélectionnez au moins un mois.", success=False); return
                ids = Expense.generate_recurring(
                    category=category, description=desc, amount=amount,
                    annee_scolaire=self._annee_scolaire,
                    months=selected_months, notes=notes,
                )
                ToastNotification(self, f"{len(ids)} dépenses récurrentes créées.", success=True)
            else:
                Expense.create({
                    "expense_type": exp_type, "category": category,
                    "description": desc, "amount": amount,
                    "month": month, "year": year,
                    "annee_scolaire": self._annee_scolaire, "notes": notes,
                })
                ToastNotification(self, "Dépense créée.", success=True)

        if self.on_save:
            self.on_save()
        self.destroy()
