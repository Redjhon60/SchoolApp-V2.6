"""
Dashboard Page
==============
Main landing page showing KPI cards and analytical charts
(students per class, registrations, re-inscriptions, departures,
transport usage). All charts update dynamically with filters.
"""

import customtkinter as ctk
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from utils.theme import COLORS, CHART_COLORS, font_title, font_subtitle, font_body
from models.dashboard_model import DashboardModel
from models.student import Student
from database.db_manager import DatabaseManager


class DashboardPage(ctk.CTkFrame):

    MONTHS_FR = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
        7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
    }

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=("#F8FAFC", "#0F172A"), **kwargs)

        self.db = DatabaseManager()
        self.current_year = self.db.get_setting("current_school_year", "2025/2026")
        self.next_year = self.db.get_setting("next_school_year", "2026/2027")

        self.selected_year = ctk.StringVar(value=self.current_year)
        self.selected_class = ctk.StringVar(value="Toutes")
        now = datetime.now()
        self.selected_month_num = now.month
        self.selected_month = ctk.StringVar(value=self.MONTHS_FR[now.month])

        self.kpi_cards = {}
        self.chart_frames = {}

        self._build_header()
        self._build_filters()
        self._build_kpi_section()
        self._build_charts_section()

        self.refresh()

    # ------------------------------------------------------------------
    # Header & Filters
    # ------------------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=25, pady=(20, 5))

        # School logo in dashboard header
        logo_path = self._get_logo_path()
        if logo_path:
            try:
                from PIL import Image
                from customtkinter import CTkImage
                img = Image.open(logo_path).convert("RGBA")
                img.thumbnail((48, 48))
                self._logo_img = CTkImage(light_image=img, dark_image=img, size=(48, 48))
                ctk.CTkLabel(header, image=self._logo_img, text="").pack(side="left", padx=(0, 10))
            except Exception:
                pass

        ctk.CTkLabel(header, text="📊 Dashboard", font=font_title()).pack(side="left")

    def _get_logo_path(self):
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("logo.jpeg", "logo.jpg", "logo.png"):
            p = os.path.join(base, "assets", "icons", name)
            if os.path.exists(p):
                return p
        return None

    def _build_filters(self):
        filter_frame = ctk.CTkFrame(
            self, fg_color=("white", COLORS["card_dark"]), corner_radius=12,
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
        )
        filter_frame.pack(fill="x", padx=25, pady=10)

        inner = ctk.CTkFrame(filter_frame, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=12)

        # School Year filter
        ctk.CTkLabel(inner, text="Année scolaire:", font=font_body()).pack(side="left", padx=(0, 8))
        years = [self.current_year, self.next_year]
        self.year_menu = ctk.CTkOptionMenu(
            inner, values=years, variable=self.selected_year,
            command=lambda v: self.refresh(), fg_color=COLORS["primary"],
            button_color=COLORS["primary_hover"], width=130,
        )
        self.year_menu.pack(side="left", padx=(0, 20))

        # Class filter
        ctk.CTkLabel(inner, text="Classe:", font=font_body()).pack(side="left", padx=(0, 8))
        self.class_menu = ctk.CTkOptionMenu(
            inner, values=["Toutes"], variable=self.selected_class,
            command=lambda v: self.refresh(), fg_color=COLORS["primary"],
            button_color=COLORS["primary_hover"], width=130,
        )
        self.class_menu.pack(side="left", padx=(0, 20))

        # Month filter
        ctk.CTkLabel(inner, text="Mois:", font=font_body()).pack(side="left", padx=(0, 8))
        month_values = [self.MONTHS_FR[m] for m in range(1, 13)]
        self.month_menu = ctk.CTkOptionMenu(
            inner, values=month_values, variable=self.selected_month,
            command=self._on_month_change, fg_color=COLORS["primary"],
            button_color=COLORS["primary_hover"], width=130,
        )
        self.month_menu.pack(side="left", padx=(0, 20))

        # Refresh button
        ctk.CTkButton(
            inner, text="🔄 Actualiser", fg_color=COLORS["secondary"],
            hover_color=COLORS["primary_hover"], command=self.refresh, width=120,
        ).pack(side="right")

    def _on_month_change(self, value):
        for num, name in self.MONTHS_FR.items():
            if name == value:
                self.selected_month_num = num
                break
        self.refresh()

    # ------------------------------------------------------------------
    # KPI Cards
    # ------------------------------------------------------------------
    def _build_kpi_section(self):
        from views.widgets import CompactKPICard

        # ── Outer container ────────────────────────────────────────────
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="x", padx=25, pady=(8, 4))

        # ── Row 1: 4 operational counters ────────────────────────────
        row1 = ctk.CTkFrame(outer, fg_color="transparent")
        row1.pack(fill="x", pady=(0, 6))
        for i in range(4):
            row1.grid_columnconfigure(i, weight=1)

        self.kpi_cards["enrolled"] = CompactKPICard(
            row1, "Élèves Inscrits", icon="🎓", color="#2563EB"
        )
        self.kpi_cards["enrolled"].grid(row=0, column=0, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["employes"] = CompactKPICard(
            row1, "Employés", icon="👥", color="#7C3AED"
        )
        self.kpi_cards["employes"].grid(row=0, column=1, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["pre_registered"] = CompactKPICard(
            row1, "Pré-inscrits (an prochain)", icon="📋", color="#0891B2"
        )
        self.kpi_cards["pre_registered"].grid(row=0, column=2, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["transport"] = CompactKPICard(
            row1, "Élèves Transport", icon="🚌", color="#D97706"
        )
        self.kpi_cards["transport"].grid(row=0, column=3, padx=4, pady=0, sticky="nsew")

        # ── Row 2: 3 revenue KPIs ─────────────────────────────────────
        row2 = ctk.CTkFrame(outer, fg_color="transparent")
        row2.pack(fill="x", pady=(0, 6))
        for i in range(3):
            row2.grid_columnconfigure(i, weight=1)

        self.kpi_cards["revenus_encaisses"] = CompactKPICard(
            row2, "Revenus Encaissés", icon="💰", color="#16A34A"
        )
        self.kpi_cards["revenus_encaisses"].grid(row=0, column=0, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["inscriptions"] = CompactKPICard(
            row2, "Inscriptions Encaissées", icon="📝", color="#0891B2"
        )
        self.kpi_cards["inscriptions"].grid(row=0, column=1, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["salaires"] = CompactKPICard(
            row2, "Salaires Payés", icon="💼", color="#EA580C"
        )
        self.kpi_cards["salaires"].grid(row=0, column=2, padx=4, pady=0, sticky="nsew")

        # ── Row 3: expenses + profit (full width) ─────────────────────
        row3 = ctk.CTkFrame(outer, fg_color="transparent")
        row3.pack(fill="x", pady=(0, 2))
        row3.grid_columnconfigure(0, weight=1)
        row3.grid_columnconfigure(1, weight=1)
        row3.grid_columnconfigure(2, weight=2)   # profit wider

        self.kpi_cards["depenses"] = CompactKPICard(
            row3, "Dépenses Payées", icon="🏦", color="#DC2626"
        )
        self.kpi_cards["depenses"].grid(row=0, column=0, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["dep_restantes"] = CompactKPICard(
            row3, "Dépenses Restantes", icon="⚠️", color="#F59E0B"
        )
        self.kpi_cards["dep_restantes"].grid(row=0, column=1, padx=4, pady=0, sticky="nsew")

        self.kpi_cards["profit"] = CompactKPICard(
            row3, "Profit Mensuel Actuel / Théorique", icon="📊", color="#047857"
        )
        self.kpi_cards["profit"].grid(row=0, column=2, padx=4, pady=0, sticky="nsew")

        # Keep legacy aliases so old update calls don't crash
        self.kpi_cards["inscription_revenue"]  = self.kpi_cards["inscriptions"]
        self.kpi_cards["monthly_income"]        = self.kpi_cards["revenus_encaisses"]
        self.kpi_cards["nb_employes"]           = self.kpi_cards["employes"]
        self.kpi_cards["salaires_payes"]        = self.kpi_cards["salaires"]
        self.kpi_cards["depenses_payees"]       = self.kpi_cards["depenses"]
        self.kpi_cards["depenses_restantes"]    = self.kpi_cards["dep_restantes"]
        self.kpi_cards["new_this_month"]        = self.kpi_cards["enrolled"]  # placeholder

    # ------------------------------------------------------------------
    # Charts
    # ------------------------------------------------------------------
    def _build_charts_section(self):
        self.charts_container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.charts_container.pack(fill="both", expand=True, padx=25, pady=10)

        for i in range(2):
            self.charts_container.grid_columnconfigure(i, weight=1)

        # Row 1: students per class (bar), monthly registrations (line)
        self.chart_frames["per_class"] = self._make_chart_card(self.charts_container, "Élèves par classe")
        self.chart_frames["per_class"].grid(row=0, column=0, padx=8, pady=8, sticky="nsew")

        self.chart_frames["monthly_reg"] = self._make_chart_card(self.charts_container, "Inscriptions mensuelles")
        self.chart_frames["monthly_reg"].grid(row=0, column=1, padx=8, pady=8, sticky="nsew")

        # Row 2: reinscription progress (donut), departures (line)
        self.chart_frames["reinscription"] = self._make_chart_card(self.charts_container, "Progression des réinscriptions")
        self.chart_frames["reinscription"].grid(row=1, column=0, padx=8, pady=8, sticky="nsew")

        self.chart_frames["departures"] = self._make_chart_card(self.charts_container, "Départs par mois")
        self.chart_frames["departures"].grid(row=1, column=1, padx=8, pady=8, sticky="nsew")

        # Row 3: transport by class (pie) - full width
        self.chart_frames["transport_class"] = self._make_chart_card(self.charts_container, "Élèves transport par classe")
        self.chart_frames["transport_class"].grid(row=2, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")

        # Row 4: Monthly income evolution (line), Payment status distribution (pie)
        self.chart_frames["income_evolution"] = self._make_chart_card(self.charts_container, "Évolution des revenus mensuels")
        self.chart_frames["income_evolution"].grid(row=3, column=0, padx=8, pady=8, sticky="nsew")

        self.chart_frames["payment_status"] = self._make_chart_card(self.charts_container, "Répartition des statuts de paiement")
        self.chart_frames["payment_status"].grid(row=3, column=1, padx=8, pady=8, sticky="nsew")

        # Row 4: income by class (bar) - full width
        self.chart_frames["income_by_class"] = self._make_chart_card(self.charts_container, "Revenus par classe")
        self.chart_frames["income_by_class"].grid(row=4, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")

        # Row 5: salary payment progress (bar)
        self.chart_frames["salary_progress"] = self._make_chart_card(self.charts_container, "Progression des Salaires (Payé / Impayé)")
        self.chart_frames["salary_progress"].grid(row=5, column=0, columnspan=2, padx=8, pady=8, sticky="nsew")

        # Row 6: Expenses by category (bar) + Fixed vs Variable (pie)
        self.chart_frames["exp_by_category"] = self._make_chart_card(self.charts_container, "Dépenses par Catégorie")
        self.chart_frames["exp_by_category"].grid(row=6, column=0, padx=8, pady=8, sticky="nsew")

        self.chart_frames["exp_fixed_vs_var"] = self._make_chart_card(self.charts_container, "Fixe vs Variable")
        self.chart_frames["exp_fixed_vs_var"].grid(row=6, column=1, padx=8, pady=8, sticky="nsew")

        # Row 7: Monthly expense evolution (line) + Paid vs Unpaid (pie)
        self.chart_frames["exp_monthly_evo"] = self._make_chart_card(self.charts_container, "Évolution Mensuelle des Dépenses")
        self.chart_frames["exp_monthly_evo"].grid(row=7, column=0, padx=8, pady=8, sticky="nsew")

        self.chart_frames["exp_paid_unpaid"] = self._make_chart_card(self.charts_container, "Dépenses Payées vs Non Payées")
        self.chart_frames["exp_paid_unpaid"].grid(row=7, column=1, padx=8, pady=8, sticky="nsew")

    def _make_chart_card(self, parent, title):
        card = ctk.CTkFrame(
            parent, corner_radius=14, fg_color=("white", COLORS["card_dark"]),
            border_width=1, border_color=("#E2E8F0", COLORS["border_dark"]),
            height=340,
        )
        ctk.CTkLabel(card, text=title, font=font_subtitle()).pack(anchor="w", padx=18, pady=(15, 5))

        canvas_holder = ctk.CTkFrame(card, fg_color="transparent")
        canvas_holder.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        card.canvas_holder = canvas_holder
        card.canvas_widget = None
        return card

    def _render_chart(self, card, fig):
        """Embed a matplotlib figure inside a chart card, replacing previous one."""
        if card.canvas_widget is not None:
            card.canvas_widget.get_tk_widget().destroy()
        canvas = FigureCanvasTkAgg(fig, master=card.canvas_holder)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)
        card.canvas_widget = canvas
        plt.close(fig)

    def _empty_fig(self, message="Aucune donnée disponible"):
        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        ax.text(0.5, 0.5, message, ha="center", va="center", fontsize=11, color="#94A3B8")
        ax.axis("off")
        return fig

    # ------------------------------------------------------------------
    # Refresh / Data loading
    # ------------------------------------------------------------------
    def refresh(self):
        year = self.selected_year.get()

        # Update class filter options
        classes = ["Toutes"] + Student.get_distinct_classes(year)
        self.class_menu.configure(values=classes)
        if self.selected_class.get() not in classes:
            self.selected_class.set("Toutes")

        self._update_kpis(year)
        self._update_charts(year)

    def _update_kpis(self, year):
        from utils.payment_constants import MONTH_CALENDAR_MAP
        from models.payment import Payment
        from models.employee import Employee
        from models.salary_payment import SalaryPayment
        from models.expense import Expense

        now            = datetime.now()
        classe         = self.selected_class.get()
        sel_month_name = self.selected_month.get()

        # Resolve selected school-year month → calendar year + month number
        start_yr = int(year.split("/")[0])
        end_yr   = int(year.split("/")[1])
        if sel_month_name in MONTH_CALENDAR_MAP:
            cal_month, offset = MONTH_CALENDAR_MAP[sel_month_name]
            cal_year = start_yr if offset == 0 else end_yr
            sal_year = str(cal_year)
        else:
            cal_month, cal_year = self.selected_month_num, now.year
            sal_year = str(cal_year)

        # ── Card 1: Élèves Inscrits ───────────────────────────────────
        try:
            enrolled = DashboardModel.kpi_current_year_count(year)
            self.kpi_cards["enrolled"].update_value(str(enrolled))
            self.kpi_cards["enrolled"].update_title("Élèves Inscrits")
        except Exception: pass

        # ── Card 2: Employés ─────────────────────────────────────────
        try:
            nb_emp = Employee.count_active()
            self.kpi_cards["employes"].update_value(str(nb_emp))
        except Exception: pass

        # ── Card 3: Revenus Encaissés / Total Revenus ─────────────────
        # Encaissés = monthly revenue for selected month (filtered)
        # Total     = sum(total_a_payer) for all students matching filters
        try:
            rev_enc   = Payment.monthly_revenue_total(year, sel_month_name, classe)
            rev_total = Payment.total_a_payer_sum(year, classe)
            self.kpi_cards["revenus_encaisses"].update_value(
                f"{rev_enc:,.0f} / {rev_total:,.0f} DH"
            )
            self.kpi_cards["revenus_encaisses"].update_title(
                f"Revenus Encaissés – {sel_month_name}"
            )
        except Exception as e:
            print(f"[KPI revenus_encaisses] {e}")

        # ── Card 4: Inscriptions Encaissées / Total Inscriptions ───────
        try:
            insc_enc   = Payment.total_inscription_revenue(year, classe)
            insc_total = Payment.total_inscription_grand_total(year)
            self.kpi_cards["inscriptions"].update_value(
                f"{insc_enc:,.0f} / {insc_total:,.0f} DH"
            )
        except Exception as e:
            print(f"[KPI inscriptions] {e}")

        # ── Card 5: Salaires Payés / Total Salaires ────────────────────
        try:
            sal_paid  = SalaryPayment.total_paid(month=sel_month_name, year=sal_year)
            sal_total = SalaryPayment.total_salary_budget()
            self.kpi_cards["salaires"].update_value(
                f"{sal_paid:,.0f} / {sal_total:,.0f} DH"
            )
            self.kpi_cards["salaires"].update_title(
                f"Salaires Payés – {sel_month_name}"
            )
        except Exception as e:
            print(f"[KPI salaires] {e}")

        # ── Card 6: Dépenses Payées / Total Dépenses ───────────────────
        try:
            exp_paid  = Expense.total_paid_expenses(annee_scolaire=year)
            exp_total = Expense.total_expenses(annee_scolaire=year)
            exp_unpaid_count = Expense.count_unpaid(annee_scolaire=year)
            self.kpi_cards["depenses"].update_value(
                f"{exp_paid:,.0f} / {exp_total:,.0f} DH"
            )
            self.kpi_cards["dep_restantes"].update_value(
                f"{exp_total - exp_paid:,.0f} DH  ({exp_unpaid_count})"
            )
        except Exception as e:
            print(f"[KPI depenses] {e}")

        # ── Card 7: Profit Mensuel Actuel / Théorique ──────────────────
        # Current  = rev_enc - exp_paid_month - sal_paid_month
        # Théorique = total_rev - total_exp  - total_sal
        try:
            exp_paid_month = Expense.total_paid_expenses(
                annee_scolaire=year, month=sel_month_name, year=sal_year
            )
            current_profit  = rev_enc - exp_paid_month - sal_paid

            total_rev_year = (
                Payment.total_inscription_revenue(year) +
                sum(Payment.monthly_revenue_total(year, m)
                    for m in MONTH_CALENDAR_MAP)
            )
            total_profit = total_rev_year - exp_total - sal_total

            self.kpi_cards["profit"].update_value(
                f"{current_profit:,.0f} / {total_profit:,.0f} DH"
            )
            self.kpi_cards["profit"].update_title(
                f"Profit {sel_month_name} / Théorique Total"
            )
        except Exception as e:
            print(f"[KPI profit] {e}")

        # ── Legacy aliases (charts & other code uses these keys) ───────
        # pre_registered + transport still needed for some chart filters
        try:
            pre_reg   = DashboardModel.kpi_pre_registered_next_year(self.next_year)
            transport = DashboardModel.kpi_transport_users(year)
            self.kpi_cards["pre_registered"].update_value(str(pre_reg))
            self.kpi_cards["transport"].update_value(str(transport))
        except Exception: pass

    def _update_charts(self, year):
        # 1. Students per class - Bar Chart
        data = DashboardModel.students_per_class(year)
        if self.selected_class.get() != "Toutes":
            data = [(c, n) for c, n in data if c == self.selected_class.get()]
        self._render_bar_chart(self.chart_frames["per_class"], data)

        # 2. Monthly registrations - Line Chart
        data = DashboardModel.monthly_registrations(year)
        self._render_line_chart(self.chart_frames["monthly_reg"], data, COLORS["primary"])

        # 3. Reinscription progress - Donut Chart
        reinscribed, eligible = DashboardModel.reinscription_progress(year, self.next_year)
        self._render_donut_chart(self.chart_frames["reinscription"], reinscribed, eligible)

        # 4. Departures by month - Line Chart
        data = DashboardModel.departures_by_month(year)
        self._render_line_chart(self.chart_frames["departures"], data, COLORS["danger"])

        # 5. Transport users by class - Pie Chart
        data = DashboardModel.transport_users_by_class(year)
        self._render_pie_chart(self.chart_frames["transport_class"], data)

        # 6. Monthly income evolution - Line Chart (3 series)
        from models.payment import Payment
        classe = self.selected_class.get()
        income_data = Payment.monthly_income_evolution(year, classe)
        self._render_income_evolution_chart(self.chart_frames["income_evolution"], income_data)

        # 7. Payment status distribution - Pie Chart
        status_data = Payment.payment_status_distribution(year, classe)
        self._render_payment_status_chart(self.chart_frames["payment_status"], status_data)

        # 8. Income by class - Bar Chart
        income_by_class = Payment.income_by_class(year)
        self._render_income_by_class_chart(self.chart_frames["income_by_class"], income_by_class)

        # 9. Salary payment progress - Stacked Bar Chart
        try:
            from models.salary_payment import SalaryPayment as SP
            sal_data = SP.salary_progress_by_month(year)
            self._render_salary_progress_chart(self.chart_frames["salary_progress"], sal_data)
        except Exception:
            pass

        # 10–13. Expense charts
        try:
            from models.expense import Expense
            self._render_exp_by_category(
                self.chart_frames["exp_by_category"],
                Expense.expenses_by_category(year),
            )
            self._render_exp_fixed_vs_var(
                self.chart_frames["exp_fixed_vs_var"],
                Expense.expenses_by_type(year),
            )
            self._render_exp_monthly_evo(
                self.chart_frames["exp_monthly_evo"],
                Expense.monthly_expense_evolution(year),
            )
            self._render_exp_paid_unpaid(
                self.chart_frames["exp_paid_unpaid"],
                Expense.total_paid_expenses(year),
                Expense.total_expenses(year) - Expense.total_paid_expenses(year),
            )
        except Exception as e:
            print(f"[EXPENSE CHART ERROR] {e}")

    # ------------------------------------------------------------------
    # Chart renderers
    # ------------------------------------------------------------------
    def _render_bar_chart(self, card, data):
        if not data:
            self._render_chart(card, self._empty_fig())
            return
        labels = [d[0] for d in data]
        values = [d[1] for d in data]

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        bars = ax.bar(labels, values, color=COLORS["primary"], width=0.55)
        ax.bar_label(bars, padding=2, fontsize=8)
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_line_chart(self, card, data, color):
        if not data:
            self._render_chart(card, self._empty_fig())
            return
        labels = [d[0] for d in data]
        values = [d[1] for d in data]

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        ax.plot(labels, values, marker="o", color=color, linewidth=2)
        ax.fill_between(range(len(values)), values, alpha=0.1, color=color)
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_donut_chart(self, card, reinscribed, eligible):
        remaining = max(eligible - reinscribed, 0)
        if eligible == 0:
            self._render_chart(card, self._empty_fig())
            return

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        values = [reinscribed, remaining]
        labels = ["Réinscrits", "En attente"]
        colors = [COLORS["success"], COLORS["border_light"]]
        wedges, texts, autotexts = ax.pie(
            values, labels=None, autopct=lambda p: f"{p:.0f}%" if p > 0 else "",
            colors=colors, startangle=90, wedgeprops=dict(width=0.4),
        )
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(1, 0.5), fontsize=8)
        ax.text(0, 0, f"{reinscribed}/{eligible}", ha="center", va="center", fontsize=14, fontweight="bold")
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_pie_chart(self, card, data):
        if not data:
            self._render_chart(card, self._empty_fig())
            return
        labels = [d[0] for d in data]
        values = [d[1] for d in data]

        fig = Figure(figsize=(8, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        colors = CHART_COLORS[: len(values)]
        ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors, startangle=90,
               textprops={"fontsize": 8})
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_income_evolution_chart(self, card, data):
        """data: list of dicts {month, inscription, mensualite, transport, total}"""
        if not data or all(d["total"] == 0 for d in data):
            self._render_chart(card, self._empty_fig())
            return

        labels = [d["month"] for d in data]
        inscription = [d["inscription"] for d in data]
        mensualite = [d["mensualite"] for d in data]
        transport = [d["transport"] for d in data]

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        ax.plot(labels, inscription, marker="o", label="Inscription", color=COLORS["secondary"], linewidth=2)
        ax.plot(labels, mensualite, marker="o", label="Mensualité", color=COLORS["success"], linewidth=2)
        ax.plot(labels, transport, marker="o", label="Transport", color=COLORS["warning"], linewidth=2)
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.legend(fontsize=8)
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_payment_status_chart(self, card, status_data):
        """status_data: {'PAYE': n, 'UNPAID': n, 'NAN': n}"""
        from utils.payment_constants import STATUS_PAYE, STATUS_UNPAID, STATUS_NAN, STATUS_LABELS, STATUS_COLORS

        values = [status_data.get(STATUS_PAYE, 0), status_data.get(STATUS_UNPAID, 0), status_data.get(STATUS_NAN, 0)]
        if sum(values) == 0:
            self._render_chart(card, self._empty_fig())
            return

        labels = [STATUS_LABELS[STATUS_PAYE], STATUS_LABELS[STATUS_UNPAID], STATUS_LABELS[STATUS_NAN]]
        colors = [STATUS_COLORS[STATUS_PAYE], STATUS_COLORS[STATUS_UNPAID], STATUS_COLORS[STATUS_NAN]]

        # Filter out zero-value slices to avoid clutter
        filtered = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
        labels, values, colors = zip(*filtered)

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        ax.pie(values, labels=labels, autopct="%1.0f%%", colors=colors, startangle=90,
               textprops={"fontsize": 8})
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_income_by_class_chart(self, card, data):
        """data: list of (classe, total_revenue)"""
        data = [(c, v) for c, v in data if v > 0]
        if not data:
            self._render_chart(card, self._empty_fig())
            return

        labels = [d[0] for d in data]
        values = [d[1] for d in data]

        fig = Figure(figsize=(10, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        bars = ax.bar(labels, values, color=COLORS["success"], width=0.6)
        ax.bar_label(bars, padding=2, fontsize=7, fmt="%.0f")
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=45, labelsize=8)
        ax.tick_params(axis="y", labelsize=8)
        fig.tight_layout()
        self._render_chart(card, fig)
    def _render_salary_progress_chart(self, card, data):
        """
        data: list of {month, paid, unpaid}
        Stacked bar chart showing paid vs unpaid salary per month.
        """
        if not data or all(d["paid"] == 0 and d["unpaid"] == 0 for d in data):
            self._render_chart(card, self._empty_fig("Aucune donnée de salaire disponible"))
            return

        labels = [d["month"] for d in data]
        paid   = [d["paid"]   for d in data]
        unpaid = [d["unpaid"] for d in data]

        fig = Figure(figsize=(10, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax  = fig.add_subplot(111)

        x = range(len(labels))
        ax.bar(x, paid,   color=COLORS["success"], label="Payé",   width=0.5)
        ax.bar(x, unpaid, color=COLORS["danger"],  label="Impayé", width=0.5, bottom=paid)

        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        ax.tick_params(axis="y", labelsize=8)
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(fontsize=8)
        fig.tight_layout()
        self._render_chart(card, fig)

    # ── Expense chart renderers ────────────────────────────────────────
    def _render_exp_by_category(self, card, data):
        """Bar chart: total expense per category."""
        data = [(c, v) for c, v in data if v > 0]
        if not data:
            self._render_chart(card, self._empty_fig()); return

        labels = [d[0] for d in data]
        values = [d[1] for d in data]
        fig    = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax = fig.add_subplot(111)
        bars = ax.barh(labels, values, color="#7C3AED")
        ax.bar_label(bars, padding=3, fontsize=7, fmt="%.0f")
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=7)
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_exp_fixed_vs_var(self, card, data):
        """Pie chart: Fixe vs Variable expenses."""
        vals   = [data.get("Fixe", 0), data.get("Variable", 0)]
        if sum(vals) == 0:
            self._render_chart(card, self._empty_fig()); return

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax  = fig.add_subplot(111)
        ax.pie(vals, labels=["Fixe", "Variable"],
               colors=["#7C3AED", "#F59E0B"],
               autopct="%1.0f%%", startangle=90,
               textprops={"fontsize": 9})
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_exp_monthly_evo(self, card, data):
        """Stacked line chart: paid + unpaid expenses per school month."""
        if not data or all(d["total"] == 0 for d in data):
            self._render_chart(card, self._empty_fig()); return

        labels = [d["month"] for d in data]
        paid   = [d["paid"]   for d in data]
        unpaid = [d["unpaid"] for d in data]

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax  = fig.add_subplot(111)
        ax.plot(labels, paid,   marker="o", color=COLORS["success"],
                label="Payé",    linewidth=2)
        ax.plot(labels, unpaid, marker="o", color=COLORS["danger"],
                label="Non Payé", linewidth=2)
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(axis="x", rotation=45, labelsize=7)
        ax.tick_params(axis="y", labelsize=7)
        ax.legend(fontsize=7)
        fig.tight_layout()
        self._render_chart(card, fig)

    def _render_exp_paid_unpaid(self, card, paid, unpaid):
        """Pie chart: paid vs unpaid expense amounts."""
        if paid + unpaid == 0:
            self._render_chart(card, self._empty_fig()); return

        fig = Figure(figsize=(5, 3), dpi=80)
        fig.patch.set_alpha(0)
        ax  = fig.add_subplot(111)
        ax.pie([paid, unpaid],
               labels=["Payé", "Non Payé"],
               colors=[COLORS["success"], COLORS["danger"]],
               autopct="%1.0f%%", startangle=90,
               textprops={"fontsize": 9})
        fig.tight_layout()
        self._render_chart(card, fig)
