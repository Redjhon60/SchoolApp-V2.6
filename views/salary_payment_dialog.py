"""
Salary Payment Dialog
======================
Modal to register a salary payment for a selected employee.
Auto-detects next unpaid month, generates PDF proof, prints it.
"""

import customtkinter as ctk
from tkinter import ttk
from datetime import datetime
import os

from utils.theme import COLORS, font_title, font_subtitle, font_body, font_button
from models.employee import Employee, SCHOOL_MONTHS
from models.salary_payment import SalaryPayment
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification, LoadingSpinner


class SalaryPaymentDialog(ctk.CTkToplevel):

    def __init__(self, master, employee_id, school_year: str, on_save=None):
        super().__init__(master)
        self.employee_id  = employee_id
        self.school_year  = school_year
        self.on_save      = on_save
        self.db           = DatabaseManager()
        self.amount_var   = ctk.StringVar()

        self.employee = Employee.get_by_id(employee_id)
        if not self.employee:
            ctk.CTkLabel(self, text="Employé introuvable.").pack(pady=40)
            return

        self.title("Paiement de Salaire")
        self.geometry("720x780")
        self.minsize(600, 640)
        self.grab_set()
        self.transient(master)

        self._build_header()
        self._center(master)
        self.after(60, self._build_body)

    def _center(self, master):
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width()  // 2) - (self.winfo_width()  // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _get_logo_path(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("logo.jpeg", "logo.jpg", "logo.png"):
            p = os.path.join(base, "assets", "icons", name)
            if os.path.exists(p): return p
        return None

    def _card(self, parent):
        return ctk.CTkFrame(
            parent, fg_color=("white", COLORS["card_dark"]), corner_radius=14,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )

    # ──────────────────────────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        logo_path = self._get_logo_path()
        if logo_path:
            try:
                from PIL import Image
                from customtkinter import CTkImage
                img = Image.open(logo_path).convert("RGBA")
                img.thumbnail((50, 50))
                self._logo = CTkImage(light_image=img, dark_image=img, size=(50, 50))
                ctk.CTkLabel(header, image=self._logo, text="").pack(
                    side="left", padx=(12, 8), pady=12
                )
            except Exception:
                pass

        e = self.employee
        nc = ctk.CTkFrame(header, fg_color="transparent")
        nc.pack(side="left", fill="y", padx=4, pady=10)
        ctk.CTkLabel(nc, text=f"{e['nom']} {e['prenom']}".strip(),
                      font=font_title(), text_color="white").pack(anchor="w")
        ctk.CTkLabel(nc, text=f"CIN: {e['cin']}  •  {e['job']}  •  Salaire: {e.get('salary',0):.0f} DH/mois",
                      font=font_body(), text_color="#CBD5E1").pack(anchor="w")

        ctk.CTkButton(
            header, text="✕", width=36, height=36, corner_radius=8,
            fg_color=COLORS["danger"], hover_color="#B91C1C",
            text_color="white", command=self.destroy,
        ).pack(side="right", padx=12, pady=12)

    def _build_body(self):
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self._build_status_section()
        self._build_form_section()
        self._build_history_section()
        self.update_idletasks()

    # ──────────────────────────────────────────────────────────────────
    # Month status chips
    # ──────────────────────────────────────────────────────────────────
    def _build_status_section(self):
        card = self._card(self.body)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(card, text="📅 Statut des salaires", font=font_subtitle()).pack(
            anchor="w", padx=18, pady=(14, 4)
        )
        self.months_row = ctk.CTkFrame(card, fg_color="transparent")
        self.months_row.pack(fill="x", padx=18, pady=(0, 4))
        self.suggestion_label = ctk.CTkLabel(card, text="", font=font_body())
        self.suggestion_label.pack(anchor="w", padx=18, pady=(0, 12))
        self._refresh_status_chips()

    def _refresh_status_chips(self):
        for w in self.months_row.winfo_children():
            w.destroy()

        paid_map   = SalaryPayment.get_paid_months(self.employee_id, self.school_year)
        next_month, next_year = SalaryPayment.get_next_unpaid_month(
            self.employee_id, self.school_year
        )

        for i, month in enumerate(SCHOOL_MONTHS):
            paid  = paid_map.get(month, False)
            color = COLORS["success"] if paid else COLORS["danger"]
            label = "Payé" if paid else "Impayé"

            chip = ctk.CTkFrame(self.months_row, fg_color=color, corner_radius=8,
                                 width=86, height=56)
            chip.grid(row=0, column=i, padx=3, pady=3, sticky="nsew")
            chip.grid_propagate(False)
            self.months_row.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(chip, text=month, font=font_body(), text_color="white").pack(pady=(7, 0))
            ctk.CTkLabel(chip, text=label, font=ctk.CTkFont(size=9), text_color="white").pack()

        if next_month:
            self.suggestion_label.configure(
                text=f"💡 Prochain mois suggéré : {next_month} {next_year}",
                text_color=COLORS["warning"],
            )
            if hasattr(self, "month_menu"):
                self.month_menu.set(next_month)
            if hasattr(self, "year_entry"):
                self.year_entry.delete(0, "end")
                self.year_entry.insert(0, next_year or "")
        else:
            self.suggestion_label.configure(
                text="✅ Tous les mois sont payés pour cette année.",
                text_color=COLORS["success"],
            )

    # ──────────────────────────────────────────────────────────────────
    # Payment form
    # ──────────────────────────────────────────────────────────────────
    def _build_form_section(self):
        card = self._card(self.body)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(card, text="💳 Enregistrer un Paiement", font=font_subtitle()).pack(
            anchor="w", padx=18, pady=(14, 4)
        )

        next_month, next_year = SalaryPayment.get_next_unpaid_month(
            self.employee_id, self.school_year
        )

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=18, pady=(0, 8))
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)

        # Month
        f1 = ctk.CTkFrame(form, fg_color="transparent")
        f1.grid(row=0, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f1, text="Mois", font=font_body(), anchor="w").pack(anchor="w")
        self.month_menu = ctk.CTkOptionMenu(
            f1, values=list(SCHOOL_MONTHS), fg_color=COLORS["primary"],
            button_color=COLORS["primary_hover"],
        )
        self.month_menu.set(next_month or SCHOOL_MONTHS[0])
        self.month_menu.pack(fill="x", pady=(2, 0))

        # Year
        f2 = ctk.CTkFrame(form, fg_color="transparent")
        f2.grid(row=0, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f2, text="Année", font=font_body(), anchor="w").pack(anchor="w")
        self.year_entry = ctk.CTkEntry(f2, font=font_body())
        self.year_entry.insert(0, next_year or str(datetime.now().year))
        self.year_entry.pack(fill="x", pady=(2, 0))

        # Amount
        f3 = ctk.CTkFrame(form, fg_color="transparent")
        f3.grid(row=1, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f3, text="Montant payé (DH)", font=font_body(), anchor="w").pack(anchor="w")
        self.amount_var.set(f"{self.employee.get('salary', 0):.0f}")
        ctk.CTkEntry(f3, textvariable=self.amount_var, font=font_body()).pack(fill="x", pady=(2, 0))

        # Payment date
        f4 = ctk.CTkFrame(form, fg_color="transparent")
        f4.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f4, text="Date de paiement (AAAA-MM-JJ)", font=font_body(), anchor="w").pack(anchor="w")
        self.date_entry = ctk.CTkEntry(f4, font=font_body())
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(fill="x", pady=(2, 0))

        # Notes
        f5 = ctk.CTkFrame(form, fg_color="transparent")
        f5.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f5, text="Notes", font=font_body(), anchor="w").pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(f5, font=font_body())
        self.notes_entry.pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            card, text="💾 Enregistrer le Paiement", font=font_button(), height=44,
            fg_color=COLORS["success"], hover_color="#16A34A",
            command=self._save_payment,
        ).pack(fill="x", padx=18, pady=(4, 16))

    # ──────────────────────────────────────────────────────────────────
    # History
    # ──────────────────────────────────────────────────────────────────
    def _build_history_section(self):
        card = self._card(self.body)
        card.pack(fill="x", pady=8)
        ctk.CTkLabel(card, text="🧾 Historique des salaires", font=font_subtitle()).pack(
            anchor="w", padx=18, pady=(14, 4)
        )
        self.hist_frame = ctk.CTkFrame(card, fg_color="transparent")
        self.hist_frame.pack(fill="x", padx=18, pady=(0, 14))
        self._refresh_history()

    def _refresh_history(self):
        for w in self.hist_frame.winfo_children():
            w.destroy()

        history = SalaryPayment.get_history(employee_id=self.employee_id)
        if not history:
            ctk.CTkLabel(self.hist_frame, text="Aucun paiement enregistré.",
                          font=font_body(), text_color=("#64748B", "#94A3B8")).pack(anchor="w")
            return

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Sal.Treeview", background="#FFFFFF", foreground="#1E293B",
                         rowheight=30, fieldbackground="#FFFFFF", borderwidth=0, font=("Segoe UI", 10))
        style.configure("Sal.Treeview.Heading", background="#2563EB", foreground="white",
                         font=("Segoe UI", 10, "bold"), relief="flat")

        cols    = ["payment_month", "payment_year", "amount_paid", "payment_date", "receipt_number", "notes"]
        headers = [("Mois", 90), ("Année", 60), ("Montant", 90), ("Date", 95), ("N° Reçu", 140), ("Notes", 160)]

        tree = ttk.Treeview(self.hist_frame, columns=cols, show="headings",
                             style="Sal.Treeview", height=min(max(len(history), 1), 6))
        for col, (lbl, w) in zip(cols, headers):
            tree.heading(col, text=lbl); tree.column(col, width=w, anchor="center")

        for p in history:
            tree.insert("", "end", values=(
                p["payment_month"], p["payment_year"],
                f"{p['amount_paid']:.0f}", p["payment_date"],
                p["receipt_number"], p.get("notes") or "",
            ))

        vsb = ttk.Scrollbar(self.hist_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ──────────────────────────────────────────────────────────────────
    # Save
    # ──────────────────────────────────────────────────────────────────
    def _save_payment(self):
        e           = self.employee
        month       = self.month_menu.get()
        year        = self.year_entry.get().strip()
        date_value  = self.date_entry.get().strip()
        notes       = self.notes_entry.get().strip()

        try:
            amount = float(self.amount_var.get())
        except ValueError:
            ToastNotification(self, "Montant invalide.", success=False); return
        if amount <= 0:
            ToastNotification(self, "Le montant doit être > 0.", success=False); return
        if not date_value:
            ToastNotification(self, "La date est obligatoire.", success=False); return
        if not year:
            ToastNotification(self, "L'année est obligatoire.", success=False); return

        if SalaryPayment.is_month_paid(self.employee_id, month, year):
            ToastNotification(self, f"Salaire {month} {year} déjà enregistré.", success=False)
            return

        spinner = LoadingSpinner(self, "Enregistrement...")
        self.update_idletasks()

        try:
            payment_data = {
                "employee_id":      self.employee_id,
                "cin":              e["cin"],
                "nom":              e["nom"],
                "prenom":           e.get("prenom", ""),
                "job":              e.get("job", ""),
                "assigned_classes": e.get("classe", ""),
                "monthly_salary":   e.get("salary", 0),
                "payment_month":    month,
                "payment_year":     year,
                "amount_paid":      amount,
                "payment_date":     date_value,
                "notes":            notes,
            }
            pay_id  = SalaryPayment.create(payment_data)
            payment = SalaryPayment.get_by_id(pay_id)

            # Generate PDF proof
            from utils.salary_proof_generator import generate_salary_proof_pdf
            proof_path = generate_salary_proof_pdf(payment, e)

            # Auto-print
            from utils.printer import print_pdf
            printed = print_pdf(proof_path)

            spinner.close()
            self._refresh_status_chips()
            self._refresh_history()
            self.notes_entry.delete(0, "end")

            msg = f"Salaire enregistré ! Reçu {payment['receipt_number']}"
            msg += " – envoyé à l'imprimante." if printed else f" – PDF: {os.path.basename(proof_path)}."
            ToastNotification(self, msg, success=True)

            if self.on_save:
                self.on_save()

        except Exception as ex:
            spinner.close()
            ToastNotification(self, f"Erreur: {ex}", success=False)
