import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
from database import (
    init_db, create_user, verify_user, add_expense, get_expenses,
    update_expense, delete_expense, set_budget, get_budgets,
    get_month_summary, get_all_categories
)
from utils.security import hash_password

st.set_page_config(page_title="SpendWise | Expense Tracker", page_icon="💸", layout="wide")
init_db()

CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Education", "Health",
              "Entertainment", "Travel", "Groceries", "Other"]

def money(value):
    return f"₹{float(value):,.2f}"

def login_screen():
    st.title("💸 SpendWise")
    st.caption("A simple, secure personal finance tracker")
    login_tab, signup_tab = st.tabs(["Login", "Create account"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            user = verify_user(username.strip(), password)
            if user:
                st.session_state.user = user
                st.rerun()
            else:
                st.error("Incorrect username or password.")

    with signup_tab:
        with st.form("signup_form"):
            new_username = st.text_input("Choose a username")
            new_password = st.text_input("Create a password", type="password")
            confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account", use_container_width=True)
        if submitted:
            if len(new_username.strip()) < 3:
                st.error("Username must contain at least 3 characters.")
            elif len(new_password) < 8:
                st.error("Use a password with at least 8 characters.")
            elif new_password != confirm:
                st.error("Passwords do not match.")
            else:
                ok = create_user(new_username.strip(), hash_password(new_password))
                if ok:
                    st.success("Account created. Please log in.")
                else:
                    st.error("That username is already taken.")

if "user" not in st.session_state:
    login_screen()
    st.stop()

user = st.session_state.user
user_id, username = user["id"], user["username"]

with st.sidebar:
    st.title("💸 SpendWise")
    st.write(f"Signed in as **{username}**")
    page = st.radio("Navigation", ["Dashboard", "Add expense", "Manage expenses", "Budgets", "Reports"])
    st.divider()
    if st.button("Log out", use_container_width=True):
        del st.session_state.user
        st.rerun()
    st.caption("Your data is stored locally in SQLite.")

st.title(page)
today = date.today()
month_start = today.replace(day=1)
expenses = get_expenses(user_id)
df = pd.DataFrame(expenses)

if page == "Dashboard":
    st.caption(f"Your financial snapshot for {today.strftime('%B %Y')}")
    summary = get_month_summary(user_id, today.year, today.month)
    income, spent = summary["income"], summary["spent"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Income recorded", money(income))
    c2.metric("Expenses this month", money(spent))
    c3.metric("Balance", money(income - spent))
    st.divider()

    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        current = df[(df["date"].dt.year == today.year) & (df["date"].dt.month == today.month)]
        left, right = st.columns(2)
        with left:
            st.subheader("Spending by category")
            if not current.empty:
                cat = current[current["kind"] == "Expense"].groupby("category", as_index=False)["amount"].sum()
                if not cat.empty:
                    st.plotly_chart(px.pie(cat, names="category", values="amount", hole=0.45), use_container_width=True)
                else:
                    st.info("No expenses recorded this month.")
            else:
                st.info("Add an expense to see your chart.")
        with right:
            st.subheader("Recent transactions")
            recent = df.sort_values("date", ascending=False).head(7)
            st.dataframe(recent[["date", "kind", "category", "description", "amount"]], hide_index=True, use_container_width=True)
    else:
        st.info("Welcome! Add your first transaction to start tracking your money.")

elif page == "Add expense":
    st.subheader("Record a transaction")
    with st.form("transaction_form", clear_on_submit=True):
        kind = st.radio("Transaction type", ["Expense", "Income"], horizontal=True)
        col1, col2 = st.columns(2)
        with col1:
            amount = st.number_input("Amount (₹)", min_value=0.01, step=50.0, format="%.2f")
            category = st.selectbox("Category", CATEGORIES if kind == "Expense" else ["Salary", "Allowance", "Business", "Other"])
        with col2:
            transaction_date = st.date_input("Date", value=today)
            description = st.text_input("Description", placeholder="e.g. Lunch, monthly salary")
        submitted = st.form_submit_button("Save transaction", use_container_width=True)
    if submitted:
        add_expense(user_id, kind, category, description.strip(), float(amount), transaction_date.isoformat())
        st.success("Transaction saved successfully.")
        st.rerun()

elif page == "Manage expenses":
    st.subheader("View, edit or delete transactions")
    if df.empty:
        st.info("No transactions yet.")
    else:
        df["date"] = pd.to_datetime(df["date"]).dt.date
        f1, f2 = st.columns(2)
        with f1:
            kind_filter = st.selectbox("Type", ["All", "Expense", "Income"])
        with f2:
            categories = ["All"] + sorted(df["category"].dropna().unique().tolist())
            cat_filter = st.selectbox("Category", categories)
        shown = df.copy()
        if kind_filter != "All":
            shown = shown[shown["kind"] == kind_filter]
        if cat_filter != "All":
            shown = shown[shown["category"] == cat_filter]
        st.dataframe(shown.sort_values("date", ascending=False), hide_index=True, use_container_width=True)

        options = {f'#{r["id"]} · {r["date"]} · {r["category"]} · {money(r["amount"])}': int(r["id"])
                   for _, r in shown.iterrows()}
        if options:
            selected_label = st.selectbox("Select a transaction to edit or delete", list(options))
            selected_id = options[selected_label]
            row = next(x for x in expenses if x["id"] == selected_id)
            with st.expander("Edit selected transaction"):
                with st.form("edit_form"):
                    e1, e2 = st.columns(2)
                    with e1:
                        new_amount = st.number_input("Amount (₹)", min_value=0.01, value=float(row["amount"]), step=50.0)
                        new_category = st.text_input("Category", value=row["category"])
                    with e2:
                        new_date = st.date_input("Date", value=date.fromisoformat(row["date"]), key="edit_date")
                        new_desc = st.text_input("Description", value=row["description"] or "")
                    save = st.form_submit_button("Save changes")
                if save:
                    update_expense(user_id, selected_id, new_category.strip(), new_desc.strip(), float(new_amount), new_date.isoformat())
                    st.success("Transaction updated.")
                    st.rerun()
            if st.button("Delete selected transaction", type="secondary"):
                delete_expense(user_id, selected_id)
                st.success("Transaction deleted.")
                st.rerun()

elif page == "Budgets":
    st.subheader("Set monthly category budgets")
    with st.form("budget_form"):
        category = st.selectbox("Category", CATEGORIES)
        amount = st.number_input("Monthly limit (₹)", min_value=1.0, step=100.0)
        submitted = st.form_submit_button("Save budget")
    if submitted:
        set_budget(user_id, category, float(amount))
        st.success("Budget saved.")
        st.rerun()

    budgets = get_budgets(user_id)
    if budgets:
        st.subheader("Your budgets")
        month_df = pd.DataFrame([x for x in expenses if x["kind"] == "Expense" and
                                 x["date"][:7] == today.strftime("%Y-%m")])
        for b in budgets:
            used = float(month_df[month_df["category"] == b["category"]]["amount"].sum()) if not month_df.empty else 0
            ratio = min(used / b["amount"], 1.0)
            st.write(f"**{b['category']}** — {money(used)} of {money(b['amount'])}")
            st.progress(ratio)
            if used > b["amount"]:
                st.warning(f"You are over your {b['category']} budget by {money(used - b['amount'])}.")
    else:
        st.info("No budgets set yet.")

elif page == "Reports":
    st.subheader("Transaction reports")
    if df.empty:
        st.info("No data available yet.")
    else:
        df["date"] = pd.to_datetime(df["date"])
        expenses_only = df[df["kind"] == "Expense"].copy()
        if not expenses_only.empty:
            expenses_only["month"] = expenses_only["date"].dt.to_period("M").astype(str)
            monthly = expenses_only.groupby("month", as_index=False)["amount"].sum()
            st.plotly_chart(px.bar(monthly, x="month", y="amount", title="Monthly expenses",
                                   labels={"month": "Month", "amount": "Amount (₹)"}), use_container_width=True)
        st.download_button("⬇️ Download all transactions as CSV",
                           data=pd.DataFrame(expenses).to_csv(index=False).encode("utf-8"),
                           file_name="spendwise_transactions.csv", mime="text/csv")
        st.caption("Reports include only transactions entered into this app.")
