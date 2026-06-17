"""
Pay Expense Dialog
===================
Modal to register payment for a specific expense.
Auto-fills amount, generates PDF receipt, auto-prints.
"""

import customtkinter as ctk
from datetime import datetime
import os

from utils.theme import COLORS, font_title, font_subtitle, font_body, font_button
from models.expense import Expense, ExpensePayment
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification, LoadingSpinner


class PayExpenseDialog(ctk.CTkToplevel):

    def __init__(self, master, expense_id, on_save=None):
        super().__init__(master)
        self.expense_id = expense_id
        self.on_save    = on_save
        self.amount_var = ctk.StringVar()

        self.expense = Expense.get_by_id(expense_id)
        if not self.expense:
            ctk.CTkLabel(self, text="Dépense introuvable.").pack(pady=30)
            return

        self.title("Payer la Dépense")
        self.geometry("560x520")
        self.minsize(480, 440)
        self.grab_set()
        self.transient(master)

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
        e = self.expense
        # Header
        hdr = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0, height=62)
        hdr.pack(fill="x")
        ctk.CTkLabel(hdr, text=f"💳 Payer – {e['category']}",
                      font=font_title(), text_color="white").pack(side="left", padx=18, pady=14)
        ctk.CTkButton(hdr, text="✕", width=36, height=36, corner_radius=8,
                       fg_color=COLORS["danger"], hover_color="#B91C1C",
                       text_color="white", command=self.destroy).pack(side="right", padx=12)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=18, pady=(0, 10))

        # Expense info card
        info = self._card(scroll)
        info.pack(fill="x", pady=8)
        ctk.CTkLabel(info, text="ℹ️ Détails de la dépense",
                      font=font_subtitle()).pack(anchor="w", padx=16, pady=(12, 4))
        grid = ctk.CTkFrame(info, fg_color="transparent")
        grid.pack(fill="x", padx=16, pady=(0, 12))
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)

        fields = [
            ("Type",        e.get("expense_type", "")),
            ("Catégorie",   e.get("category", "")),
            ("Description", e.get("description", "") or "-"),
            ("Période",     f"{e.get('month','')} {e.get('year','')}"),
            ("Montant",     f"{e.get('amount', 0):,.2f} DH"),
        ]
        for i, (lbl, val) in enumerate(fields):
            r, col = divmod(i, 2)
            f = ctk.CTkFrame(grid, fg_color="transparent")
            f.grid(row=r, column=col, sticky="w", padx=8, pady=4)
            ctk.CTkLabel(f, text=lbl, font=font_body(),
                          text_color=("#64748B", "#94A3B8")).pack(anchor="w")
            ctk.CTkLabel(f, text=str(val), font=font_subtitle()).pack(anchor="w")

        # Payment form card
        form = self._card(scroll)
        form.pack(fill="x", pady=8)
        ctk.CTkLabel(form, text="💰 Paiement",
                      font=font_subtitle()).pack(anchor="w", padx=16, pady=(12, 4))

        fg = ctk.CTkFrame(form, fg_color="transparent")
        fg.pack(fill="x", padx=16, pady=(0, 6))
        fg.grid_columnconfigure(0, weight=1)
        fg.grid_columnconfigure(1, weight=1)

        # Amount paid
        fa = ctk.CTkFrame(fg, fg_color="transparent")
        fa.grid(row=0, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(fa, text="Montant payé (DH)", font=font_body(), anchor="w").pack(anchor="w")
        self.amount_var.set(f"{e.get('amount', 0):.0f}")
        ctk.CTkEntry(fa, textvariable=self.amount_var, font=font_body()).pack(fill="x", pady=(2, 0))

        # Date
        fd = ctk.CTkFrame(fg, fg_color="transparent")
        fd.grid(row=0, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(fd, text="Date de paiement (AAAA-MM-JJ)", font=font_body(), anchor="w").pack(anchor="w")
        self.date_entry = ctk.CTkEntry(fd, font=font_body())
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(fill="x", pady=(2, 0))

        # Notes
        fn = ctk.CTkFrame(fg, fg_color="transparent")
        fn.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(fn, text="Notes", font=font_body(), anchor="w").pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(fn, font=font_body())
        self.notes_entry.pack(fill="x", pady=(2, 0))

        ctk.CTkButton(form, text="💾 Enregistrer le Paiement",
                       font=font_button(), height=44,
                       fg_color=COLORS["success"], hover_color="#16A34A",
                       command=self._save).pack(fill="x", padx=16, pady=(4, 16))

    def _save(self):
        date_value = self.date_entry.get().strip()
        notes      = self.notes_entry.get().strip()
        try:
            amount = float(self.amount_var.get())
        except ValueError:
            ToastNotification(self, "Montant invalide.", success=False); return
        if amount <= 0:
            ToastNotification(self, "Le montant doit être > 0.", success=False); return
        if not date_value:
            ToastNotification(self, "La date est obligatoire.", success=False); return

        spinner = LoadingSpinner(self, "Enregistrement…")
        self.update_idletasks()
        try:
            payment = ExpensePayment.pay_expense(
                self.expense_id, amount, date_value, notes
            )
            # Generate PDF receipt
            from utils.expense_receipt_generator import generate_expense_receipt_pdf
            exp    = Expense.get_by_id(self.expense_id)
            path   = generate_expense_receipt_pdf(exp, payment)

            # Auto-print
            from utils.printer import print_pdf
            printed = print_pdf(path)

            spinner.close()
            msg = f"Paiement enregistré ! Reçu {payment['receipt_number']}"
            msg += " – imprimé." if printed else f" – PDF: {os.path.basename(path)}."
            ToastNotification(self, msg, success=True)

            if self.on_save:
                self.on_save()
            self.destroy()
        except Exception as ex:
            spinner.close()
            ToastNotification(self, f"Erreur: {ex}", success=False)
