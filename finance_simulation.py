"""
Financial Simulation Models

This module defines classes and logic for simulating personal finances,
including net worth evolution, properties (with loans), incomes,
expenses, and events (buy/sell property, add/remove income/expense).
"""

# ================================================================
# Global Constants
# ================================================================
DEFAULT_ANNUAL_RETURN = 0.029  # Net annual return on investments


# ================================================================
# Utility Functions
# ================================================================
def format_eur(amount: float) -> str:
    """
    Format a number according to French convention:
    - Non-breaking space (\u00A0) as thousands separator
    - Append euro symbol
    """
    return f"{amount:,.0f}".replace(",", "\u00A0") + " €"


# ================================================================
# Core Domain Classes
# ================================================================
class NetWorth:
    """Represents global financial situation (cash, investments, properties)."""

    def __init__(self, cash: float, investments: float, properties: list):
        self.cash = cash
        self.investments = investments
        self.properties = properties

    def compute_networth(self) -> float:
        """Compute total net worth = cash + investments + (property value - debts)."""
        return self.cash + self.investments + sum(p.gross_value - p.debt for p in self.properties)


class Property:
    """Represents a real estate property (with optional loan)."""

    def __init__(
        self,
        name: str,
        gross_value: float,
        buying_taxes: float,
        debt: float,
        taxe_fonciere: float,
        charges_copro: float,
        loan_amount: float = 0,
        loan_duration: int = 0,
        loan_interest_rate: float = 0,
    ):
        self.name = name
        self.gross_value = gross_value
        self.buying_taxes = buying_taxes
        self.debt = debt
        self.taxe_fonciere = taxe_fonciere
        self.charges_copro = charges_copro
        self.loan_amount = loan_amount
        self.loan_duration = loan_duration
        self.loan_interest_rate = loan_interest_rate

        self.loan_monthly_payment, self.yearly_amortization = self._compute_loan_details()

    def _compute_loan_details(self) -> tuple[float, float]:
        """Compute loan monthly payment and yearly amortization, if applicable."""
        n = self.loan_duration * 12
        r = self.loan_interest_rate / 12

        if n > 0 and r > 0:
            # Standard annuity formula for monthly payment
            monthly_payment = round(
                self.loan_amount / (((1 + r) ** n - 1) / (r * (1 + r) ** n)),
                2,
            )
            yearly_amortization = self.loan_amount / self.loan_duration
            return monthly_payment, yearly_amortization
        return 0, 0

    def __str__(self) -> str:
        return (
            f"**Property {self.name}**: Gross value: **{format_eur(self.gross_value)}** - "
            f"Debt: {format_eur(self.debt)}  \n"
            f"_Yearly fees_: Taxe Foncière ({format_eur(self.taxe_fonciere)}) + "
            f"Charges ({format_eur(self.charges_copro)})  \n"
            f"_Loan_: {self.loan_duration} years, monthly payment: {format_eur(self.loan_monthly_payment)}"
        )


class Expense:
    """Represents a recurring yearly expense."""

    def __init__(self, name: str, yearly_amount: float):
        self.name = name
        self.yearly_amount = yearly_amount

    def __str__(self) -> str:
        return f"**{self.name}** - Yearly amount: {format_eur(self.yearly_amount)}"


class Income:
    """Represents a recurring yearly income."""

    def __init__(self, name: str, yearly_amount: float):
        self.name = name
        self.yearly_amount = yearly_amount

    def __str__(self) -> str:
        return f"**{self.name}** - Yearly amount: {format_eur(self.yearly_amount)}"


# ================================================================
# Event System
# ================================================================
class Event:
    """Represents a financial event at a specific year (buy/sell property, add/remove income/expense)."""

    def __init__(self, year: int, action: str, payload):
        self.year = year
        self.action = action
        self.payload = payload

    def apply(self, simulation: "Simulation") -> None:
        """Apply this event to a simulation."""
        if self.action == "Add income":
            simulation.incomes.append(self.payload)

        elif self.action == "Remove income":
            simulation.incomes = [i for i in simulation.incomes if i.name != self.payload["name"]]

        elif self.action == "Add expense":
            simulation.expenses.append(self.payload)

        elif self.action == "Remove expense":
            simulation.expenses = [e for e in simulation.expenses if e.name != self.payload["name"]]

        elif self.action == "Buy property":
            self._apply_buy_property(simulation)

        elif self.action == "Sell property":
            self._apply_sell_property(simulation)

    def _apply_buy_property(self, simulation: "Simulation") -> None:
        """Handle property purchase: deduct cost from investments/cash, add property."""
        prop = self.payload
        total_cost = prop.gross_value + prop.buying_taxes

        # Deduct from investments first, then cash if needed
        if simulation.networth.investments >= total_cost:
            simulation.networth.investments -= total_cost
        else:
            remaining = total_cost - simulation.networth.investments
            simulation.networth.investments = 0
            simulation.networth.cash -= remaining

        simulation.networth.properties.append(prop)

    def _apply_sell_property(self, simulation: "Simulation") -> None:
        """Handle property sale: add proceeds to cash, remove property."""
        prop = next((p for p in simulation.networth.properties if p.name == self.payload["name"]), None)
        if prop:
            # Assume gross value - debt - fixed selling costs
            simulation.networth.cash += prop.gross_value - prop.debt - 1000
            simulation.networth.properties.remove(prop)

    def __str__(self) -> str:
        return f"Event: year={self.year}, action={self.action}, payload={self.payload}"


# ================================================================
# Simulation Engine
# ================================================================
class Simulation:
    """Engine that runs financial simulations over time."""

    def __init__(self, networth: NetWorth, incomes: list, expenses: list, events: list, r_annual: float = DEFAULT_ANNUAL_RETURN):
        self.current_year = 0
        self.networth = networth
        self.incomes = incomes
        self.expenses = expenses
        self.events = sorted(events, key=lambda e: e.year)
        self.r_annual = r_annual
        self.simulation_results = []

    # -----------------------------
    # Core loop
    # -----------------------------
    def run(self, years: int) -> None:
        """Run the simulation for a given number of years."""
        for y in range(1, years + 1):
            self.current_year = y
            self._apply_yearly_events()
            self._update_loans()
            self._apply_expenses_and_incomes()
            self._grow_investments()
            self._record_results()

    # -----------------------------
    # Internal helpers
    # -----------------------------
    def _apply_yearly_events(self) -> None:
        """Apply events scheduled for the current year."""
        for event in [e for e in self.events if e.year == self.current_year]:
            event.apply(self)

    def _update_loans(self) -> None:
        """Update debts and loan durations for all properties."""
        for prop in self.networth.properties:
            if prop.loan_duration > 0:
                prop.debt = round(prop.debt - prop.yearly_amortization, 2)
                prop.loan_duration -= 1
            else:
                prop.debt = 0
                prop.loan_monthly_payment = 0

    def _apply_expenses_and_incomes(self) -> None:
        """Apply yearly incomes and expenses to cash and investments."""
        # Property-related expenses
        property_expenses = sum(
            p.taxe_fonciere + p.charges_copro + p.loan_monthly_payment * 12
            for p in self.networth.properties
        )

        # All expenses
        total_expenses = sum(e.yearly_amount for e in self.expenses) + property_expenses

        # Net income available for investment
        available_for_investment = sum(i.yearly_amount for i in self.incomes) - total_expenses

        # Add to cash, then invest all cash at year end
        self.networth.cash += available_for_investment
        self.networth.investments += self.networth.cash
        self.networth.cash = 0

    def _grow_investments(self) -> None:
        """Apply annual return to investments."""
        self.networth.investments = round(self.networth.investments * (1 + self.r_annual), 2)

    def _record_results(self) -> None:
        """Store results for the current year."""
        available_for_investment = (
            sum(i.yearly_amount for i in self.incomes)
            - sum(e.yearly_amount for e in self.expenses)
            - sum(p.taxe_fonciere + p.charges_copro + p.loan_monthly_payment * 12 for p in self.networth.properties)
        )
        self.simulation_results.append({
            "Year": self.current_year,
            "Available for investment": available_for_investment,
            "Investments total": self.networth.investments,
            "Net worth": self.networth.compute_networth(),
        })

    # -----------------------------
    # Public helpers
    # -----------------------------
    def __str__(self) -> str:
        return f"Simulation results: {self.simulation_results}"

    def reset(self) -> None:
        """Reset simulation state (clears results)."""
        self.current_year = 0
        self.simulation_results = []
