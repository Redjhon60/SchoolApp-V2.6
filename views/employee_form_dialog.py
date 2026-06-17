"""
Employee Form Dialog
=====================
Modal for adding or editing an employee.
When Job = "Professeur", shows a multi-select class assignment panel
populated from student classes already in the DB.
"""

import customtkinter as ctk
from datetime import datetime

from utils.theme import COLORS, font_title, font_subtitle, font_body, font_button
from models.employee import Employee
from models.student import Student
from views.widgets import ToastNotification


class EmployeeFormDialog(ctk.CTkToplevel):

    def __init__(self, master, employee_id=None, on_save=None):
        super().__init__(master)
        self.employee_id = employee_id
        self.on_save     = on_save
        self.is_edit     = employee_id is not None
        self._class_vars = {}       # checkbox vars for class assignment
        self._selected_job = ctk.StringVar()

        title = "Modifier l'employé" if self.is_edit else "Ajouter un employé"
        self.title(title)
        self.geometry("640x680")
        self.minsize(560, 560)
        self.grab_set()
        self.transient(master)

        self._existing = Employee.get_by_id(employee_id) if self.is_edit else {}
        self._build_ui()
        self._center(master)

    def _center(self, master):
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width()  // 2) - (self.winfo_width()  // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["primary"], corner_radius=0, height=64)
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text=("✏️ Modifier l'employé" if self.is_edit else "➕ Ajouter un employé"),
            font=font_title(), text_color="white",
        ).pack(side="left", padx=20, pady=16)

        ctk.CTkButton(
            header, text="✕", width=36, height=36, corner_radius=8,
            fg_color=COLORS["danger"], hover_color="#B91C1C",
            text_color="white", command=self.destroy,
        ).pack(side="right", padx=14)

        # Scrollable form
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=10)
        scroll.grid_columnconfigure(0, weight=1)
        scroll.grid_columnconfigure(1, weight=1)

        e = self._existing

        self.cin_entry    = self._field(scroll, "CIN *", e.get("cin", ""), 0, 0, 2)
        self.nom_entry    = self._field(scroll, "Nom *", e.get("nom", ""), 1, 0)
        self.prenom_entry = self._field(scroll, "Prénom", e.get("prenom", ""), 1, 1)

        # Job dropdown
        f_job = ctk.CTkFrame(scroll, fg_color="transparent")
        f_job.grid(row=2, column=0, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f_job, text="Poste / Job *", font=font_body(), anchor="w").pack(anchor="w")
        jobs = ["Professeur", "Directeur", "Surveillant", "Secrétaire",
                "Agent d'entretien", "Comptable", "Autre"]
        self.job_menu = ctk.CTkOptionMenu(
            f_job, values=jobs, variable=self._selected_job,
            fg_color=COLORS["primary"], button_color=COLORS["primary_hover"],
            command=self._on_job_change,
        )
        self.job_menu.set(e.get("job") or jobs[0])
        self.job_menu.pack(fill="x", pady=(2, 0))

        self.salary_entry     = self._field(scroll, "Salaire (DH)", str(e.get("salary") or ""), 2, 1)
        self.start_date_entry = self._field(scroll, "Date début (AAAA-MM-JJ)", e.get("start_date", ""), 3, 0)
        self.note_entry       = self._field(scroll, "Note", e.get("note", ""), 3, 1)

        # Class assignment panel (shown only for Professeur)
        self.class_panel = ctk.CTkFrame(
            scroll, fg_color=("white", COLORS["card_dark"]), corner_radius=10,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        self.class_panel.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=10)
        ctk.CTkLabel(self.class_panel, text="📚 Classes assignées", font=font_subtitle()).pack(
            anchor="w", padx=14, pady=(10, 4)
        )
        self._class_checks_frame = ctk.CTkFrame(self.class_panel, fg_color="transparent")
        self._class_checks_frame.pack(fill="x", padx=14, pady=(0, 10))
        self._build_class_checkboxes()

        # Save button
        ctk.CTkButton(
            scroll, text="💾 Enregistrer", font=font_button(), height=44,
            fg_color=COLORS["success"], hover_color="#16A34A",
            command=self._save,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=8, pady=16)

        # Show/hide class panel based on current job
        self._on_job_change(self.job_menu.get())

    def _field(self, parent, label, value, row, col, colspan=1):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text=label, font=font_body(), anchor="w").pack(anchor="w")
        entry = ctk.CTkEntry(f, font=font_body())
        entry.insert(0, str(value) if value is not None else "")
        entry.pack(fill="x", pady=(2, 0))
        return entry

    def _build_class_checkboxes(self):
        for w in self._class_checks_frame.winfo_children():
            w.destroy()
        self._class_vars.clear()

        # Load classes from student DB + any saved on this employee
        student_classes = Student.get_distinct_classes()
        saved = [c.strip() for c in (self._existing.get("classe") or "").split(",") if c.strip()]
        all_classes = sorted(set(student_classes) | set(saved))

        if not all_classes:
            ctk.CTkLabel(self._class_checks_frame, text="(Aucune classe disponible – importez des élèves)",
                          font=font_body(), text_color=("#64748B", "#94A3B8")).pack(anchor="w")
            return

        for i, cls in enumerate(all_classes):
            var = ctk.BooleanVar(value=(cls in saved))
            chk = ctk.CTkCheckBox(
                self._class_checks_frame, text=cls, variable=var,
                font=font_body(), checkbox_width=20, checkbox_height=20,
            )
            chk.grid(row=i // 4, column=i % 4, sticky="w", padx=8, pady=3)
            self._class_vars[cls] = var

        self._class_checks_frame.grid_columnconfigure(tuple(range(4)), weight=1)

    def _on_job_change(self, value):
        if value == "Professeur":
            self.class_panel.grid()
        else:
            self.class_panel.grid_remove()

    def _save(self):
        cin    = self.cin_entry.get().strip()
        nom    = self.nom_entry.get().strip()
        prenom = self.prenom_entry.get().strip()
        job    = self.job_menu.get()
        salary_str = self.salary_entry.get().strip()

        if not cin:
            ToastNotification(self, "Le CIN est obligatoire.", success=False); return
        if not nom:
            ToastNotification(self, "Le nom est obligatoire.", success=False); return

        try:
            salary = float(salary_str) if salary_str else 0.0
        except ValueError:
            ToastNotification(self, "Le salaire doit être un nombre.", success=False); return

        # Collect assigned classes
        classe = ""
        if job == "Professeur":
            selected = [cls for cls, var in self._class_vars.items() if var.get()]
            classe = ", ".join(sorted(selected))

        record = {
            "cin":        cin,
            "nom":        nom,
            "prenom":     prenom,
            "job":        job,
            "classe":     classe,
            "salary":     salary,
            "start_date": self.start_date_entry.get().strip(),
            "note":       self.note_entry.get().strip(),
        }

        if self.is_edit:
            # Check CIN uniqueness if changed
            existing_other = Employee.get_by_cin(cin)
            if existing_other and existing_other["id"] != self.employee_id:
                ToastNotification(self, f"CIN {cin} déjà utilisé.", success=False); return
            Employee.update(self.employee_id, record)
            ToastNotification(self, "Employé modifié avec succès.", success=True)
        else:
            if Employee.get_by_cin(cin):
                ToastNotification(self, f"CIN {cin} déjà existant.", success=False); return
            Employee.create(record)
            ToastNotification(self, f"Employé {nom} {prenom} créé.", success=True)

        if self.on_save:
            self.on_save()
        self.destroy()
