import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "database" / "expenses.db"

def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('Expense','Income')),
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL CHECK(amount > 0),
            date TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount > 0),
            UNIQUE(user_id, category),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)

def create_user(username, password_hash):
    try:
        with get_connection() as conn:
            cur = conn.execute("INSERT INTO users(username,password_hash) VALUES(?,?)",
                               (username, password_hash))
            return cur.lastrowid
    except sqlite3.IntegrityError:
        return None

def verify_user(username, password):
    from utils.security import verify_password
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if row and verify_password(password, row["password_hash"]):
        return {"id": row["id"], "username": row["username"]}
    return None

def add_expense(user_id, kind, category, description, amount, transaction_date):
    with get_connection() as conn:
        conn.execute("""INSERT INTO transactions(user_id,kind,category,description,amount,date)
                        VALUES(?,?,?,?,?,?)""",
                     (user_id, kind, category, description, amount, transaction_date))

def get_expenses(user_id):
    with get_connection() as conn:
        rows = conn.execute("""SELECT id,kind,category,description,amount,date
                               FROM transactions WHERE user_id=? ORDER BY date DESC,id DESC""",
                            (user_id,)).fetchall()
    return [dict(r) for r in rows]

def update_expense(user_id, transaction_id, category, description, amount, transaction_date):
    with get_connection() as conn:
        conn.execute("""UPDATE transactions SET category=?,description=?,amount=?,date=?
                        WHERE id=? AND user_id=?""",
                     (category, description, amount, transaction_date, transaction_id, user_id))

def delete_expense(user_id, transaction_id):
    with get_connection() as conn:
        conn.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (transaction_id, user_id))

def set_budget(user_id, category, amount):
    with get_connection() as conn:
        conn.execute("""INSERT INTO budgets(user_id,category,amount) VALUES(?,?,?)
                        ON CONFLICT(user_id,category) DO UPDATE SET amount=excluded.amount""",
                     (user_id, category, amount))

def get_budgets(user_id):
    with get_connection() as conn:
        rows = conn.execute("SELECT category,amount FROM budgets WHERE user_id=? ORDER BY category",
                            (user_id,)).fetchall()
    return [dict(r) for r in rows]

def get_month_summary(user_id, year, month):
    month_key = f"{year:04d}-{month:02d}"
    with get_connection() as conn:
        rows = conn.execute("""SELECT kind,COALESCE(SUM(amount),0) AS total
                               FROM transactions WHERE user_id=? AND substr(date,1,7)=?
                               GROUP BY kind""", (user_id, month_key)).fetchall()
    totals = {r["kind"]: r["total"] for r in rows}
    return {"income": float(totals.get("Income", 0)), "spent": float(totals.get("Expense", 0))}

def get_all_categories(user_id):
    with get_connection() as conn:
        rows = conn.execute("SELECT DISTINCT category FROM transactions WHERE user_id=?", (user_id,)).fetchall()
    return [r["category"] for r in rows]
