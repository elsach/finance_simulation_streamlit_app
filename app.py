"""
Streamlit Application: Net Worth Simulation

This app allows users to simulate their net worth evolution over time
by setting initial financial parameters, adding properties, incomes,
expenses, and events (buy/sell property, add/remove income/expense).
"""

import copy
import pandas as pd
import plotly.express as px
import streamlit as st
from finance_simulation import Property, Income, Expense, NetWorth, Event, Simulation


# ================================================================
# Utility functions
# ================================================================
def format_eur(amount: float) -> str:
    """
    Format a number according to French convention:
    - Non-breaking space as thousands separator
    - Append euro symbol
    """
    return f"{amount:,.0f}".replace(",", "\u00A0") + " €"


def get_current_properties(session_state, year: int) -> list[str]:
    """
    Return list of currently owned properties (by name) at a given year.
    Takes into account past "Buy property" and "Sell property" events.
    """
    current = [p.name for p in session_state.init_properties]

    for e in session_state.events:
        if e.action == "Sell property" and e.payload["name"] in current:
            current.remove(e.payload["name"])
        if e.action == "Buy property" and e.year < year:
            current.append(e.payload.name)

    return current


def get_current_incomes(session_state, year: int) -> list[str]:
    """
    Return list of active incomes (by name) at a given year.
    Takes into account "Add income" and "Remove income" events.
    """
    current = []
    for e in session_state.events:
        if e.action == "Remove income" and e.payload["name"] in current:
            current.remove(e.payload["name"])
        if e.action == "Add income" and e.year < year:
            current.append(e.payload.name)
    return current


def get_current_expenses(session_state, year: int) -> list[str]:
    """
    Return list of active expenses (by name) at a given year.
    Takes into account "Add expense" and "Remove expense" events.
    """
    current = []
    for e in session_state.events:
        if e.action == "Remove expense" and e.payload["name"] in current:
            current.remove(e.payload["name"])
        if e.action == "Add expense" and e.year < year:
            current.append(e.payload.name)
    return current


# ================================================================
# Streamlit Page Config
# ================================================================
st.set_page_config(
    page_title="Networth simulator",
    layout="wide",
    initial_sidebar_state="auto",
    page_icon="💰"
)

# Initialize state containers
if "simulations" not in st.session_state:
    st.session_state.simulations = {}
if "init_properties" not in st.session_state:
    st.session_state.init_properties = []
if "events" not in st.session_state:
    st.session_state.events = []

st.title("💰 Net Worth Simulation App 💰")

# ------------------------------------------------
# Layout with 3 main columns
# ------------------------------------------------
initial_col, events_col, recap_col = st.columns([2, 2, 3])

# ================================================================
# LEFT PANEL: Initial Setup
# ================================================================
with initial_col:
    st.header("Initial Setup")

    # --- Basic financials ---
    col1, col2 = st.columns(2)
    with col1:
        initial_cash = st.number_input("Initial cash", value=0, step=1000, key="initial_cash")
        salary = st.number_input("Annual salary", value=0, step=1000, key="initial_income")
    with col2:
        initial_investments = st.number_input("Initial investments", value=0, step=1000, key="initial_investments")
        living_expenses = st.number_input("Annual living expenses", value=0, step=1000, key="initial_expenses")

    # --- Initial properties ---
    st.subheader("Initial Properties")

    with st.form("add_property_form", clear_on_submit=True):
        prop_col1, prop_col2 = st.columns(2)
        with prop_col1:
            prop_name = st.text_input("Property name", "Property")
            taxe_fonciere = st.number_input("Taxe foncière", value=0, step=100)
        with prop_col2:
            prop_value = st.number_input("Gross value", value=0, step=1000)
            charges_copro = st.number_input("Charges copro (annual)", value=0, step=100)

        # Optional loan details
        with st.expander("Loan Details", expanded=False):
            loan_col1, loan_col2 = st.columns(2)
            with loan_col1:
                prop_debt = st.number_input("Debt", value=0, step=1000)
                loan_duration = st.number_input("Loan duration (years)", value=0)
            with loan_col2:
                loan_amount = st.number_input("Loan amount", value=0, step=1000)
                loan_rate = st.number_input(
                    "Loan interest rate (%)",
                    min_value=0.0, max_value=100.0,
                    value=0.0, step=0.1, format="%.2f"
                )

        submitted = st.form_submit_button("Add Property")
        if submitted:
            if not prop_name:
                st.warning("Please enter a name for the property.")
            elif prop_name in [p.name for p in st.session_state.init_properties]:
                st.warning(f"A property named '{prop_name}' already exists.")
            else:
                st.session_state.init_properties.append(
                    Property(
                        prop_name, prop_value, 0, prop_debt, taxe_fonciere, charges_copro,
                        loan_amount, loan_duration, loan_rate / 100.0
                    )
                )
                st.success(f"Property '{prop_name}' added.")

# ================================================================
# MIDDLE PANEL: Events
# ================================================================
with events_col:
    st.header("Simulation Events")

    # --- Event year & action ---
    col1, col2 = st.columns([1, 2])
    with col1:
        year = st.number_input("Event Year", min_value=1, value=1, key="event_year")
    with col2:
        action = st.selectbox(
            "Action",
            ["Add income", "Remove income", "Add expense", "Remove expense", "Buy property", "Sell property"]
        )

    # --- Event payload (depends on action) ---
    payload = None
    if action == "Add income":
        name = st.text_input("Income name")
        amount = st.number_input("Yearly amount", value=0)
        payload = Income(name, amount)

    elif action == "Remove income":
        options = get_current_incomes(st.session_state, year)
        name = st.selectbox("Income to remove", options, key=f"remove_income_{year}_{len(st.session_state.events)}")
        payload = {"name": name}

    elif action == "Add expense":
        name = st.text_input("Expense name")
        amount = st.number_input("Yearly amount", value=0)
        payload = Expense(name, amount)

    elif action == "Remove expense":
        options = get_current_expenses(st.session_state, year)
        name = st.selectbox("Expense to remove", options, key=f"remove_expense_{year}_{len(st.session_state.events)}")
        payload = {"name": name}

    elif action == "Buy property":
        name = st.text_input("Property name", "Property 1")
        prop_col1, prop_col2 = st.columns(2)
        with prop_col1:
            value = st.number_input("Gross value", value=0, step=1000)
            taxe = st.number_input("Taxe foncière", value=0, step=100)
        with prop_col2:
            buying_taxes = st.number_input("Buying taxes", value=0, step=1000)
            charges = st.number_input("Charges copro (annual)", value=0, step=100)

        with st.expander("Loan Details", expanded=False):
            loan_col1, loan_col2 = st.columns(2)
            with loan_col1:
                debt = st.number_input("Debt", value=0, step=1000)
                duration = st.number_input("Loan duration (years)", value=0)
            with loan_col2:
                loan_amount = st.number_input("Loan amount", value=0, step=1000)
                rate = st.number_input("Loan interest rate (%)", min_value=0.0, max_value=100.0, value=0.0, step=0.1)

        payload = Property(name, value, buying_taxes, debt, taxe, charges, loan_amount, duration, rate / 100.0)

    elif action == "Sell property":
        options = get_current_properties(st.session_state, year)
        name = st.selectbox("Property to sell", options, key=f"sell_{year}_{len(st.session_state.events)}")
        payload = {"name": name}

    # --- Submit event ---
    with st.form("add_event_form", clear_on_submit=True):
        submitted = st.form_submit_button("Add Event")
        if submitted:
            if action in ("Add income", "Add expense", "Buy property") and not payload.name.strip():
                st.warning(f"Please enter a name for the {action.split('_')[1]}.")
            elif action in ("Add income", "Add expense", "Buy property"):
                existing = [
                    e.payload.name for e in st.session_state.events
                    if e.action == action and hasattr(e.payload, "name")
                ]
                if payload.name in existing:
                    st.warning(f"A {action.split('_')[1]} named '{payload.name}' already exists.")
                else:
                    st.session_state.events.append(Event(year, action, payload))
                    st.success(f"Event '{action}' added at year {year}.")
                    st.rerun()
            else:
                st.session_state.events.append(Event(year, action, payload))
                st.success(f"Event '{action}' added at year {year}.")
                st.rerun()

# ================================================================
# RIGHT PANEL: Recap
# ================================================================
with recap_col:
    st.header("Simulation Recap")

    # --- Initial state recap ---
    st.subheader("Initial State")
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Initial cash:** {format_eur(initial_cash)}")
        st.write(f"**Salary:** {format_eur(salary)}")
    with col2:
        st.write(f"**Initial investments:** {format_eur(initial_investments)}")
        st.write(f"**Living expenses:** {format_eur(living_expenses)}")

    # Properties recap
    if st.session_state.init_properties:
        st.markdown("**Properties:**")
        for i, p in enumerate(st.session_state.init_properties):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"{i+1}. {p}", unsafe_allow_html=True)
            with col2:
                if st.button("🗑️", key=f"remove_prop_{i}"):
                    st.session_state.init_properties.pop(i)
                    st.rerun()
    else:
        st.write("_No properties added yet_")

    # --- Events recap ---
    st.subheader("Events")
    if st.session_state.events:
        st.session_state.events.sort(key=lambda e: e.year)
        for i, e in enumerate(st.session_state.events):
            col1, col2 = st.columns([4, 1])
            with col1:
                if e.action in ("Add income", "Add expense", "Buy property"):
                    st.write(f"{i+1}. **_Year {e.year}_** - {e.action}:  \n{e.payload}")
                else:
                    st.write(f"{i+1}. **_Year {e.year}_** - {e.action}: **{e.payload['name']}**")
            with col2:
                if st.button("🗑️", key=f"remove_event_{i}"):
                    st.session_state.events.pop(i)
                    st.rerun()
    else:
        st.write("_No events added yet_")

    # --- Save simulation config ---
    st.subheader("Add simulation")
    simulation_name = st.text_input("Simulation name")
    if st.button("Add simulation"):
        if not simulation_name:
            st.warning("Please enter a name for the simulation.")
        elif simulation_name in st.session_state.simulations:
            st.warning(f"A simulation named '{simulation_name}' already exists.")
        else:
            networth = NetWorth(0, initial_investments + initial_cash, copy.deepcopy(st.session_state.init_properties))
            incomes = [Income("Salary", salary)]
            expenses = [Expense("Living expenses", living_expenses)]
            st.session_state.simulations[simulation_name] = {
                "initial_cash": initial_cash,
                "initial_investments": initial_investments,
                "init_properties": copy.deepcopy(st.session_state.init_properties),
                "salary": salary,
                "living_expenses": living_expenses,
                "events": copy.deepcopy(st.session_state.events),
            }
            st.success(f"Simulation '{simulation_name}' added.")

# ================================================================
# SIDEBAR: Simulation management + Run
# ================================================================
st.sidebar.title("My simulations")

with st.sidebar:
    if st.session_state.simulations:
        for i, sim in enumerate(st.session_state.simulations):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"{i+1}. {sim}")
            with col2:
                if st.button("🗑️", key=f"remove_simulation_{i}"):
                    st.session_state.simulations.pop(sim)
                    st.rerun()
    else:
        st.write("_No simulations added yet_")

years = st.sidebar.slider("Years to simulate", min_value=1, max_value=50, value=20)
annual_return = st.sidebar.number_input(
                    "Investment annual return rate (%)",
                    min_value=0.0, max_value=100.0,
                    value=3.0, step=0.1, format="%.2f"
                )

# --- Run simulations ---
if st.sidebar.button("Run simulations"):
    if st.session_state.simulations:
        results_by_sim = {}
        for sim_name, cfg in st.session_state.simulations.items():
            networth = NetWorth(0, cfg["initial_investments"] + cfg["initial_cash"], copy.deepcopy(cfg["init_properties"]))
            incomes = [Income("Salary", cfg["salary"])]
            expenses = [Expense("Living expenses", cfg["living_expenses"])]
            sim = Simulation(networth, copy.deepcopy(incomes), copy.deepcopy(expenses), copy.deepcopy(cfg["events"]), r_annual=annual_return/100)
            sim.run(years=years)
            results_by_sim[sim_name] = sim.simulation_results

        # Build dataframe for visualization
        df = pd.concat(
            [
                pd.DataFrame(results_by_sim[name]).assign(Simulation=name, Year=range(1, len(results_by_sim[name]) + 1))
                for name in results_by_sim
            ],
            ignore_index=True,
        )[["Simulation", "Year", "Net worth"]]

        fig = px.line(df, x="Year", y="Net worth", color="Simulation", title="Net Worth Evolution Over Time")
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.sidebar.warning("_No simulations to run yet_")
