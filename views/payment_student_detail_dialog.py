"""
Payment Student Detail Dialog
===============================
Modal popup: student info, monthly status chips, payment form,
payment history.  Header has Close (✕) and Minimize (—) buttons.
Body is deferred via after() to guarantee rendering on Windows.
"""

import customtkinter as ctk
from tkinter import ttk
from datetime import datetime
import os

from utils.theme import COLORS, font_title, font_subtitle, font_body, font_button
from utils.payment_constants import (
    SCHOOL_MONTHS, PAYMENT_TYPES, STATUS_LABELS, STATUS_COLORS, STATUS_UNPAID,
)
from models.payment_student import PaymentStudent
from models.payment import Payment
from database.db_manager import DatabaseManager
from views.widgets import ToastNotification, LoadingSpinner


class PaymentStudentDetailDialog(ctk.CTkToplevel):

    def __init__(self, master, student_id, on_change=None):
        super().__init__(master)
        self.title("Détails de l'élève – Paiements")
        self.geometry("800x860")
        self.minsize(680, 640)
        self.grab_set()
        self.transient(master)

        self.db         = DatabaseManager()
        self.student_id = student_id
        self.on_change  = on_change
        self._minimized = False
        self.amount_var = ctk.StringVar()

        self.student = PaymentStudent.get_by_id(student_id)
        if not self.student:
            ctk.CTkLabel(self, text="Élève introuvable.", font=font_subtitle()).pack(pady=40)
            return

        # Build header immediately (lightweight, no CTkScrollableFrame)
        self._build_header()
        self._center_on_parent(master)

        # Build the heavy body after the window is mapped so Windows
        # renders the CTkScrollableFrame children correctly
        self.after(60, self._build_body)

    # ──────────────────────────────────────────────────────────────────
    # Positioning
    # ──────────────────────────────────────────────────────────────────
    def _center_on_parent(self, master):
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width()  // 2) - (self.winfo_width()  // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    # ──────────────────────────────────────────────────────────────────
    # Header  (built immediately)
    # ──────────────────────────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0, height=82)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Logo
        logo_path = self._get_logo_path()
        if logo_path:
            try:
                from PIL import Image
                from customtkinter import CTkImage
                img = Image.open(logo_path).convert("RGBA")
                img.thumbnail((54, 54))
                self._logo_ctk = CTkImage(light_image=img, dark_image=img, size=(54, 54))
                ctk.CTkLabel(header, image=self._logo_ctk, text="").pack(
                    side="left", padx=(14, 8), pady=14
                )
            except Exception:
                pass

        # Name + meta
        name_col = ctk.CTkFrame(header, fg_color="transparent")
        name_col.pack(side="left", fill="y", padx=4, pady=10)
        full_name = f"{self.student['eleve_nom']} {self.student['eleve_prenom']}".strip()
        ctk.CTkLabel(name_col, text=full_name,
                      font=font_title(), text_color="white").pack(anchor="w")
        ctk.CTkLabel(
            name_col,
            text=(f"Matricule: {self.student['matricule']}  •  "
                  f"{self.student['classe']}  •  {self.student['annee_scolaire']}"),
            font=font_body(), text_color="#CBD5E1",
        ).pack(anchor="w")

        # Window-control buttons (right)
        ctrl = ctk.CTkFrame(header, fg_color="transparent")
        ctrl.pack(side="right", padx=14, pady=14)

        ctk.CTkButton(
            ctrl, text="—", width=36, height=36, corner_radius=8,
            fg_color=COLORS["primary_hover"], hover_color=COLORS["secondary"],
            text_color="white", font=ctk.CTkFont(size=16, weight="bold"),
            command=self._toggle_minimize,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            ctrl, text="✕", width=36, height=36, corner_radius=8,
            fg_color=COLORS["danger"], hover_color="#B91C1C",
            text_color="white", font=ctk.CTkFont(size=13, weight="bold"),
            command=self.destroy,
        ).pack(side="left", padx=4)

    # ──────────────────────────────────────────────────────────────────
    # Body  (deferred so it renders correctly on Windows)
    # ──────────────────────────────────────────────────────────────────
    def _build_body(self):
        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=18, pady=(0, 12))

        self._build_info_section()
        self._build_month_status_section()
        self._build_payment_form_section()
        self._build_history_section()

        # Force geometry update so children are visible
        self.update_idletasks()

    # ──────────────────────────────────────────────────────────────────
    # Minimize / restore
    # ──────────────────────────────────────────────────────────────────
    def _toggle_minimize(self):
        if self._minimized:
            if hasattr(self, "body"):
                self.body.pack(fill="both", expand=True, padx=18, pady=(0, 12))
            self.geometry("800x860")
            self._minimized = False
        else:
            if hasattr(self, "body"):
                self.body.pack_forget()
            self.geometry("800x84")
            self._minimized = True

    # ──────────────────────────────────────────────────────────────────
    # Logo helper
    # ──────────────────────────────────────────────────────────────────
    def _get_logo_path(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("logo.jpeg", "logo.jpg", "logo.png"):
            p = os.path.join(base, "assets", "icons", name)
            if os.path.exists(p):
                return p
        return None

    # ──────────────────────────────────────────────────────────────────
    # Card helper
    # ──────────────────────────────────────────────────────────────────
    def _card(self, parent):
        return ctk.CTkFrame(
            parent, fg_color=("white", COLORS["card_dark"]), corner_radius=14,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )

    # ──────────────────────────────────────────────────────────────────
    # Student info
    # ──────────────────────────────────────────────────────────────────
    def _build_info_section(self):
        card = self._card(self.body)
        card.pack(fill="x", pady=8)

        ctk.CTkLabel(card, text="ℹ️ Informations de l'élève",
                      font=font_subtitle()).pack(anchor="w", padx=18, pady=(14, 4))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=18, pady=(0, 14))
        for i in range(3):
            grid.grid_columnconfigure(i, weight=1)

        s          = self.student
        total_paid = PaymentStudent.get_total_paid(s["id"], s["annee_scolaire"])

        fields = [
            ("Matricule",          s["matricule"]),
            ("Nom",                s["eleve_nom"]),
            ("Prénom",             s.get("eleve_prenom") or "-"),
            ("Classe",             s["classe"]),
            ("Année scolaire",     s["annee_scolaire"]),
            ("Inscription",        s.get("inscription") or "-"),
            ("Transport (DH)",     f"{s.get('transport', 0):.0f}"),
            ("Mensualité (DH)",    f"{s.get('mensualite', 0):.0f}"),
            ("Total à payer (DH)", f"{s.get('total_a_payer', 0):.0f}"),
            ("Note/Date",          s.get("note_date") or "-"),
        ]

        for idx, (label, value) in enumerate(fields):
            r, col = divmod(idx, 3)
            f = ctk.CTkFrame(grid, fg_color="transparent")
            f.grid(row=r, column=col, sticky="w", padx=8, pady=5)
            ctk.CTkLabel(f, text=label, font=font_body(),
                          text_color=("#64748B", "#94A3B8")).pack(anchor="w")
            ctk.CTkLabel(f, text=str(value), font=font_subtitle()).pack(anchor="w")

        # Total paid – refreshed after each payment
        r, col = divmod(len(fields), 3)
        f = ctk.CTkFrame(grid, fg_color="transparent")
        f.grid(row=r, column=col, sticky="w", padx=8, pady=5)
        ctk.CTkLabel(f, text="Total payé (DH)", font=font_body(),
                      text_color=("#64748B", "#94A3B8")).pack(anchor="w")
        self.total_paid_label = ctk.CTkLabel(
            f, text=f"{total_paid:.0f}", font=font_subtitle(),
            text_color=COLORS["success"]
        )
        self.total_paid_label.pack(anchor="w")

    # ──────────────────────────────────────────────────────────────────
    # Monthly status chips
    # ──────────────────────────────────────────────────────────────────
    def _build_month_status_section(self):
        self.status_card = self._card(self.body)
        self.status_card.pack(fill="x", pady=8)

        ctk.CTkLabel(self.status_card, text="📅 Statut Mensuel",
                      font=font_subtitle()).pack(anchor="w", padx=18, pady=(14, 4))

        self.months_row = ctk.CTkFrame(self.status_card, fg_color="transparent")
        self.months_row.pack(fill="x", padx=18, pady=(0, 4))

        self.suggestion_label = ctk.CTkLabel(
            self.status_card, text="", font=font_body()
        )
        self.suggestion_label.pack(anchor="w", padx=18, pady=(0, 12))

        self._refresh_month_status()

    def _refresh_month_status(self):
        for w in self.months_row.winfo_children():
            w.destroy()

        s          = self.student
        statuses   = PaymentStudent.get_month_statuses(s["id"], s["annee_scolaire"])
        next_month = PaymentStudent.get_next_unpaid_month(s["id"], s["annee_scolaire"])

        for i, month in enumerate(SCHOOL_MONTHS):
            status = statuses.get(month, STATUS_UNPAID)
            color  = STATUS_COLORS.get(status, STATUS_COLORS[STATUS_UNPAID])
            lbl    = STATUS_LABELS.get(status, "")

            chip = ctk.CTkFrame(
                self.months_row, fg_color=color, corner_radius=8, width=88, height=58
            )
            chip.grid(row=0, column=i, padx=3, pady=3, sticky="nsew")
            chip.grid_propagate(False)
            self.months_row.grid_columnconfigure(i, weight=1)

            ctk.CTkLabel(chip, text=month, font=font_body(),
                          text_color="white").pack(pady=(8, 0))
            ctk.CTkLabel(chip, text=lbl, font=ctk.CTkFont(size=9),
                          text_color="white").pack()

        if next_month:
            self.suggestion_label.configure(
                text=f"💡 Mois suggéré : {next_month}",
                text_color=COLORS["warning"],
            )
            if hasattr(self, "month_menu"):
                self.month_menu.set(next_month)
        else:
            self.suggestion_label.configure(
                text="✅ Tous les mois sont à jour.",
                text_color=COLORS["success"],
            )

    # ──────────────────────────────────────────────────────────────────
    # Payment form
    # ──────────────────────────────────────────────────────────────────
    def _build_payment_form_section(self):
        card = self._card(self.body)
        card.pack(fill="x", pady=8)

        ctk.CTkLabel(card, text="➕ Ajouter Paiement",
                      font=font_subtitle()).pack(anchor="w", padx=18, pady=(14, 4))

        form = ctk.CTkFrame(card, fg_color="transparent")
        form.pack(fill="x", padx=18, pady=(0, 8))
        form.grid_columnconfigure(0, weight=1)
        form.grid_columnconfigure(1, weight=1)

        next_month = PaymentStudent.get_next_unpaid_month(
            self.student["id"], self.student["annee_scolaire"]
        )

        # Row 0 — type + month
        f1 = ctk.CTkFrame(form, fg_color="transparent")
        f1.grid(row=0, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f1, text="Type de paiement",
                      font=font_body(), anchor="w").pack(anchor="w")
        self.payment_type_menu = ctk.CTkOptionMenu(
            f1, values=PAYMENT_TYPES, fg_color=COLORS["primary"],
            button_color=COLORS["primary_hover"],
            command=self._on_type_change,
        )
        self.payment_type_menu.set("Mensualité")
        self.payment_type_menu.pack(fill="x", pady=(2, 0))

        f2 = ctk.CTkFrame(form, fg_color="transparent")
        f2.grid(row=0, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f2, text="Mois", font=font_body(), anchor="w").pack(anchor="w")
        self.month_menu = ctk.CTkOptionMenu(
            f2, values=list(SCHOOL_MONTHS), fg_color=COLORS["primary"],
            button_color=COLORS["primary_hover"],
        )
        self.month_menu.set(next_month if next_month else SCHOOL_MONTHS[0])
        self.month_menu.pack(fill="x", pady=(2, 0))

        # Row 1 — amount + date
        f3 = ctk.CTkFrame(form, fg_color="transparent")
        f3.grid(row=1, column=0, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f3, text="Montant (DH)", font=font_body(), anchor="w").pack(anchor="w")
        ctk.CTkEntry(f3, textvariable=self.amount_var, font=font_body()).pack(
            fill="x", pady=(2, 0)
        )

        f4 = ctk.CTkFrame(form, fg_color="transparent")
        f4.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f4, text="Date (AAAA-MM-JJ)", font=font_body(), anchor="w").pack(anchor="w")
        self.date_entry = ctk.CTkEntry(f4, font=font_body())
        self.date_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))
        self.date_entry.pack(fill="x", pady=(2, 0))

        # Row 2 — notes
        f5 = ctk.CTkFrame(form, fg_color="transparent")
        f5.grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=5)
        ctk.CTkLabel(f5, text="Notes", font=font_body(), anchor="w").pack(anchor="w")
        self.notes_entry = ctk.CTkEntry(f5, font=font_body())
        self.notes_entry.pack(fill="x", pady=(2, 0))

        # Pre-fill amount
        self._on_type_change("Mensualité")

        ctk.CTkButton(
            card, text="💾 Enregistrer le Paiement", font=font_button(), height=44,
            fg_color=COLORS["success"], hover_color="#16A34A",
            command=self._save_payment,
        ).pack(fill="x", padx=18, pady=(4, 16))

    def _on_type_change(self, value):
        s = self.student
        if value == "Mensualité":
            self.amount_var.set(f"{s.get('mensualite', 0):.0f}")
            if hasattr(self, "month_menu"):
                self.month_menu.configure(state="normal")
        elif value == "Transport":
            self.amount_var.set(f"{s.get('transport', 0):.0f}")
            if hasattr(self, "month_menu"):
                self.month_menu.configure(state="disabled")
        else:
            self.amount_var.set("")
            if hasattr(self, "month_menu"):
                self.month_menu.configure(state="disabled")

    # ──────────────────────────────────────────────────────────────────
    # Payment history
    # ──────────────────────────────────────────────────────────────────
    def _build_history_section(self):
        self.history_card = self._card(self.body)
        self.history_card.pack(fill="x", pady=8)

        ctk.CTkLabel(self.history_card, text="🧾 Historique des paiements",
                      font=font_subtitle()).pack(anchor="w", padx=18, pady=(14, 4))

        self.history_body = ctk.CTkFrame(self.history_card, fg_color="transparent")
        self.history_body.pack(fill="x", expand=True, padx=18, pady=(0, 14))

        self._refresh_history()

    def _refresh_history(self):
        for w in self.history_body.winfo_children():
            w.destroy()

        history = Payment.get_history(self.student["id"], self.student["annee_scolaire"])
        if not history:
            ctk.CTkLabel(
                self.history_body, text="Aucun paiement enregistré pour cette année.",
                font=font_body(), text_color=("#64748B", "#94A3B8"),
            ).pack(anchor="w")
            return

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("PayD.Treeview", background="#FFFFFF", foreground="#1E293B",
                         rowheight=30, fieldbackground="#FFFFFF", borderwidth=0,
                         font=("Segoe UI", 10))
        style.configure("PayD.Treeview.Heading", background="#2563EB", foreground="white",
                         font=("Segoe UI", 10, "bold"), relief="flat")

        cols    = ["payment_type", "month", "amount", "payment_date", "receipt_number", "notes"]
        headers = [("Type", 95), ("Mois", 85), ("Montant", 90),
                   ("Date", 95), ("N° Reçu", 140), ("Notes", 160)]

        tree = ttk.Treeview(
            self.history_body, columns=cols, show="headings",
            style="PayD.Treeview", height=min(max(len(history), 1), 8),
        )
        for col, (lbl, w) in zip(cols, headers):
            tree.heading(col, text=lbl)
            tree.column(col, width=w, anchor="center")

        for p in history:
            tree.insert("", "end", values=(
                p["payment_type"], p.get("month") or "-",
                f"{p['amount']:.0f}", p["payment_date"],
                p["receipt_number"], p.get("notes") or "",
            ))

        vsb = ttk.Scrollbar(self.history_body, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    # ──────────────────────────────────────────────────────────────────
    # Save payment
    # ──────────────────────────────────────────────────────────────────
    def _save_payment(self):
        s            = self.student
        year         = s["annee_scolaire"]
        payment_type = self.payment_type_menu.get()
        month        = self.month_menu.get() if payment_type == "Mensualité" else None
        date_value   = self.date_entry.get().strip()
        notes        = self.notes_entry.get().strip()

        try:
            amount = float(self.amount_var.get())
        except ValueError:
            ToastNotification(self, message="Le montant doit être un nombre valide.", success=False)
            return
        if amount <= 0:
            ToastNotification(self, message="Le montant doit être supérieur à 0.", success=False)
            return
        if not date_value:
            ToastNotification(self, message="La date de paiement est obligatoire.", success=False)
            return

        spinner = LoadingSpinner(self, "Enregistrement du paiement...")
        self.update_idletasks()

        try:
            payment = Payment.register_payment(
                student_id     = s["id"],
                annee_scolaire = year,
                payment_type   = payment_type,
                month          = month,
                amount         = amount,
                payment_date   = date_value,
                notes          = notes,
            )

            total_paid = PaymentStudent.get_total_paid(s["id"], year)
            total_due  = s.get("total_a_payer", 0) or 0
            remaining  = max(total_due - total_paid, 0)

            # Generate PDF receipt
            from utils.receipt_generator import generate_receipt_pdf
            receipt_path = generate_receipt_pdf(
                payment=payment, student=s, remaining_amount=remaining,
                logo_path=self._get_logo_path(),
            )

            # Persist receipt metadata
            self.db.execute(
                "INSERT OR IGNORE INTO receipts "
                "(receipt_number, payment_id, file_path, date_creation) VALUES (?,?,?,?)",
                (payment["receipt_number"], payment["id"], receipt_path,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )

            # Auto-print
            from utils.printer import print_pdf
            printed = print_pdf(receipt_path)

            spinner.close()

            # Refresh UI in-place
            self.total_paid_label.configure(text=f"{total_paid:.0f}")
            self._refresh_month_status()
            self._refresh_history()
            self.notes_entry.delete(0, "end")

            msg = f"Paiement enregistré ! Reçu {payment['receipt_number']}"
            msg += " – envoyé à l'imprimante." if printed else \
                   f" – PDF: {os.path.basename(receipt_path)}."
            ToastNotification(self, message=msg, success=True)

            if self.on_change:
                self.on_change()

        except Exception as e:
            spinner.close()
            ToastNotification(self, message=f"Erreur: {e}", success=False)
