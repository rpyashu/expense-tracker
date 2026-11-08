import csv
import io
import math
import sqlite3
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, g, jsonify, Response)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "change-this-to-a-long-random-string"
DATABASE = "expenses.db"

# sign: +1 adds to your balance, -1 deducts from it
ENTRY_TYPES = {
    "expense": {
        "label": "Expense", "sign": -1, "party": False,
        "category_label": "Category", "mode_label": "Paid with",
        "hint": "Money you spent. Deducted from your balance.",
        "categories": ["Food & Dining", "Groceries", "Rent", "Bills & Utilities",
                       "Transport", "Fuel", "Shopping", "Health", "Education",
                       "Entertainment", "Travel", "Subscriptions", "EMI",
                       "Insurance", "Gifts", "Personal Care", "Other"],
    },
    "income": {
        "label": "Extra income", "sign": 1, "party": False,
        "category_label": "Source", "mode_label": "Received in",
        "hint": "Bonus, freelance, refund or any money on top of your salary.",
        "categories": ["Bonus", "Freelance", "Interest", "Refund",
                       "Gift received", "Lent money returned", "Other income"],
    },
    "borrowed": {
        "label": "Borrowed", "sign": 1, "party": True,
        "category_label": "Borrowed from", "mode_label": "Received in",
        "hint": "Money you borrowed. It adds to your balance, and you owe it back.",
        "categories": ["Friend", "Family", "Bank loan", "Credit card", "Other"],
    },
    "repayment": {
        "label": "Loan repaid", "sign": -1, "party": True,
        "category_label": "Repaid to", "mode_label": "Paid with",
        "hint": "Money you paid back on something you borrowed.",
        "categories": ["Friend", "Family", "Bank loan", "Credit card", "Other"],
    },
    "lent": {
        "label": "Lent", "sign": -1, "party": True,
        "category_label": "Lent to", "mode_label": "Paid with",
        "hint": "Money you gave to someone. Add it as extra income when it returns.",
        "categories": ["Friend", "Family", "Other"],
    },
    "savings": {
        "label": "Savings", "sign": -1, "party": False,
        "category_label": "Saved in", "mode_label": "Paid with",
        "hint": "Money you set aside or invested.",
        "categories": ["Emergency fund", "Fixed deposit", "Mutual fund",
                       "Stocks", "Gold", "Other"],
    },
}
PAYMENT_METHODS = ["UPI", "Debit card", "Credit card", "Cash",
                   "Net banking", "Wallet", "Cheque", "Other"]
ALL_CATEGORIES = sorted({c for t in ENTRY_TYPES.values() for c in t["categories"]})


# ---------- Formatting ----------
@app.template_filter("inr")
def format_inr(value):
    """Format a number as rupees with Indian digit grouping, e.g. ₹12,34,567.00"""
    value = round(value or 0, 2)
    sign = "−" if value < 0 else ""
    whole, fraction = f"{abs(value):.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{sign}₹{whole}.{fraction}"


# ---------- Database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        with open("schema.sql") as f:
            db.executescript(f.read())
        # Upgrade older databases that were created before the 'party' column
        columns = [row["name"] for row in db.execute("PRAGMA table_info(expenses)")]
        if "party" not in columns:
            db.execute("ALTER TABLE expenses ADD COLUMN party TEXT")
        db.commit()


# ---------- Small helpers ----------
def parse_amount(raw):
    """Return a positive finite number, or 0 if the value is not valid."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0
    return value if math.isfinite(value) and value > 0 else 0


def valid_iso_date(value):
    try:
        date.fromisoformat(value or "")
        return True
    except ValueError:
        return False


def normalize_month(value):
    """'2026-3' or '2026-03' -> '2026-03'. Returns None if invalid."""
    try:
        return datetime.strptime(value or "", "%Y-%m").strftime("%Y-%m")
    except ValueError:
        return None


def get_plans(user_id):
    return get_db().execute(
        "SELECT * FROM income_plans WHERE user_id = ? "
        "ORDER BY effective_from, id",
        (user_id,),
    ).fetchall()


def plan_for_month(plans, year_month):
    """The income plan that applies to a month: the latest one that started on or before it."""
    current = None
    for plan in plans:
        if plan["effective_from"] <= year_month:
            current = plan
    return current


def monthly_income(plans, year_month):
    plan = plan_for_month(plans, year_month)
    return plan["annual_amount"] / 12 if plan else 0.0


# ---------- Login protection ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


# ---------- Auth routes ----------
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        error = None
        if not name or not email or not password:
            error = "All fields are required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."

        if error is None:
            db = get_db()
            try:
                db.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                db.commit()
            except sqlite3.IntegrityError:
                error = "That email is already registered."
            else:
                flash("Account created. Please log in.", "success")
                return redirect(url_for("login"))

        flash(error, "error")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Overview (yearly balance) ----------
@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    try:
        year = int(request.args.get("year", date.today().year))
    except ValueError:
        year = date.today().year
    year = max(2000, min(year, 2100))

    db = get_db()
    plans = get_plans(uid)
    yearly_income = sum(monthly_income(plans, f"{year}-{m:02d}") for m in range(1, 13))

    totals = {key: 0.0 for key in ENTRY_TYPES}
    rows = db.execute(
        "SELECT type, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? AND strftime('%Y', expense_date) = ? GROUP BY type",
        (uid, str(year)),
    ).fetchall()
    for row in rows:
        if row["type"] in totals:
            totals[row["type"]] = row["total"]

    added = totals["income"] + totals["borrowed"]
    deducted = totals["expense"] + totals["repayment"] + totals["lent"] + totals["savings"]
    available = yearly_income + added
    balance = available - deducted
    used_pct = min(100, deducted / available * 100) if available > 0 else (100 if deducted > 0 else 0)

    breakdown = [
        {"label": t["label"], "sign": t["sign"], "total": totals[key]}
        for key, t in ENTRY_TYPES.items()
    ]

    recent_rows = db.execute(
        "SELECT * FROM expenses WHERE user_id = ? "
        "ORDER BY expense_date DESC, id DESC LIMIT 5",
        (uid,),
    ).fetchall()
    recent = []
    for r in recent_rows:
        info = ENTRY_TYPES.get(r["type"], ENTRY_TYPES["expense"])
        recent.append(dict(r, sign=info["sign"], type_label=info["label"]))

    return render_template(
        "dashboard.html",
        year=year, has_plan=bool(plans),
        yearly_income=yearly_income, added=added, deducted=deducted,
        available=available, balance=balance, used_pct=used_pct,
        breakdown=breakdown, recent=recent,
    )


# ---------- Yearly income plans ----------
@app.route("/income")
@login_required
def income():
    plans = get_plans(session["user_id"])
    today_month = date.today().strftime("%Y-%m")
    current = plan_for_month(plans, today_month)
    return render_template(
        "income.html",
        plans=list(reversed(plans)),
        current_annual=current["annual_amount"] if current else None,
        today_month=today_month,
    )


@app.route("/income/add", methods=["POST"])
@login_required
def add_income_plan():
    annual = parse_amount(request.form.get("annual_amount"))
    month = normalize_month(request.form.get("effective_from"))
    label = request.form.get("label", "").strip()[:60]

    if annual <= 0 or month is None:
        flash("Enter a yearly income and a valid month.", "error")
        return redirect(url_for("income"))

    db = get_db()
    db.execute(
        "INSERT INTO income_plans (user_id, annual_amount, effective_from, label) "
        "VALUES (?, ?, ?, ?)",
        (session["user_id"], annual, month, label),
    )
    db.commit()
    flash("Income saved.", "success")
    return redirect(url_for("income"))


@app.route("/income/<int:plan_id>/update", methods=["POST"])
@login_required
def update_income_plan(plan_id):
    data = request.get_json(silent=True) or {}
    annual = parse_amount(data.get("annual_amount"))
    month = normalize_month(data.get("effective_from"))
    label = (data.get("label") or "").strip()[:60]

    if annual <= 0 or month is None:
        return jsonify(ok=False, error="Enter a yearly income and a valid month."), 400

    db = get_db()
    db.execute(
        "UPDATE income_plans SET annual_amount = ?, effective_from = ?, label = ? "
        "WHERE id = ? AND user_id = ?",
        (annual, month, label, plan_id, session["user_id"]),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/income/<int:plan_id>/delete", methods=["POST"])
@login_required
def delete_income_plan(plan_id):
    db = get_db()
    db.execute(
        "DELETE FROM income_plans WHERE id = ? AND user_id = ?",
        (plan_id, session["user_id"]),
    )
    db.commit()
    flash("Income entry deleted.", "success")
    return redirect(url_for("income"))


# ---------- Entries (spreadsheet view) ----------
@app.route("/expenses")
@login_required
def expenses():
    db = get_db()
    rows = db.execute(
        "SELECT * FROM expenses WHERE user_id = ? "
        "ORDER BY expense_date DESC, id DESC",
        (session["user_id"],),
    ).fetchall()
    entries = [
        dict(r, positive=ENTRY_TYPES.get(r["type"], {}).get("sign", -1) > 0)
        for r in rows
    ]
    return render_template(
        "expenses.html",
        expenses=entries, entry_types=ENTRY_TYPES,
        all_categories=ALL_CATEGORIES, methods=PAYMENT_METHODS,
    )


@app.route("/expenses/add", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        entry_type = request.form.get("type", "")
        amount = parse_amount(request.form.get("amount"))
        category = request.form.get("category", "").strip()[:40]
        expense_date = request.form.get("expense_date", "")
        payment_method = request.form.get("payment_method", "").strip()[:40] or "Other"
        party = request.form.get("party", "").strip()[:60]
        note = request.form.get("note", "").strip()[:120]

        error = None
        if entry_type not in ENTRY_TYPES:
            error = "Please choose a type."
        elif amount <= 0:
            error = "Enter an amount greater than 0."
        elif not category:
            error = "Choose or type a category."
        elif not valid_iso_date(expense_date):
            error = "Please choose a valid date."

        if error:
            flash(error, "error")
        else:
            if not ENTRY_TYPES[entry_type]["party"]:
                party = ""
            db = get_db()
            db.execute(
                "INSERT INTO expenses (user_id, amount, category, type, "
                "expense_date, payment_method, party, note) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session["user_id"], amount, category, entry_type,
                 expense_date, payment_method, party, note),
            )
            db.commit()
            flash("Entry saved.", "success")
            return redirect(url_for("dashboard"))

    return render_template(
        "add_expense.html",
        entry_types=ENTRY_TYPES, methods=PAYMENT_METHODS,
        today=date.today().isoformat(),
        values=request.form if request.method == "POST" else {},
    )


@app.route("/expenses/<int:expense_id>/update", methods=["POST"])
@login_required
def update_expense(expense_id):
    data = request.get_json(silent=True) or {}

    entry_type = data.get("type")
    amount = parse_amount(data.get("amount"))
    category = (data.get("category") or "").strip()[:40]
    expense_date = data.get("expense_date", "")
    payment_method = (data.get("payment_method") or "").strip()[:40] or "Other"
    party = (data.get("party") or "").strip()[:60]
    note = (data.get("note") or "").strip()[:120]

    if (entry_type not in ENTRY_TYPES or amount <= 0 or not category
            or not valid_iso_date(expense_date)):
        return jsonify(ok=False, error="Please check the values in this row."), 400

    db = get_db()
    db.execute(
        "UPDATE expenses SET amount = ?, category = ?, type = ?, "
        "expense_date = ?, payment_method = ?, party = ?, note = ? "
        "WHERE id = ? AND user_id = ?",
        (amount, category, entry_type, expense_date, payment_method,
         party, note, expense_id, session["user_id"]),
    )
    db.commit()
    return jsonify(ok=True)


@app.route("/expenses/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    db = get_db()
    db.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"]),
    )
    db.commit()
    flash("Entry deleted.", "success")
    return redirect(url_for("expenses"))


# ---------- Export to Excel (CSV) ----------
@app.route("/expenses/export")
@login_required
def export_csv():
    db = get_db()
    rows = db.execute(
        "SELECT expense_date, type, category, party, note, payment_method, amount "
        "FROM expenses WHERE user_id = ? ORDER BY expense_date DESC",
        (session["user_id"],),
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Type", "Category", "Person", "Note", "Payment mode", "Amount"])
    for r in rows:
        label = ENTRY_TYPES.get(r["type"], {}).get("label", r["type"])
        writer.writerow([r["expense_date"], label, r["category"], r["party"],
                         r["note"], r["payment_method"], r["amount"]])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=expenses.csv"},
    )


# ---------- Monthly summary ----------
def parse_month(value):
    try:
        return datetime.strptime(value, "%Y-%m")
    except (TypeError, ValueError):
        return datetime.today().replace(day=1)


@app.route("/summary")
@login_required
def summary():
    uid = session["user_id"]
    first = parse_month(request.args.get("month"))
    month = first.strftime("%Y-%m")
    prev = first - timedelta(days=1)          # last day of the previous month
    prev_month = prev.strftime("%Y-%m")
    db = get_db()
    plans = get_plans(uid)

    def month_totals(m):
        return db.execute(
            "SELECT "
            "COALESCE(SUM(CASE WHEN type = 'income' THEN amount END), 0) AS extra, "
            "COALESCE(SUM(CASE WHEN type = 'expense' THEN amount END), 0) AS spent "
            "FROM expenses WHERE user_id = ? AND strftime('%Y-%m', expense_date) = ?",
            (uid, m),
        ).fetchone()

    current = month_totals(month)
    previous = month_totals(prev_month)

    change = None
    if previous["spent"] > 0:
        change = (current["spent"] - previous["spent"]) / previous["spent"] * 100

    categories = db.execute(
        "SELECT category, SUM(amount) AS total, COUNT(*) AS entries "
        "FROM expenses WHERE user_id = ? AND type = 'expense' "
        "AND strftime('%Y-%m', expense_date) = ? "
        "GROUP BY category ORDER BY total DESC",
        (uid, month),
    ).fetchall()

    trend = db.execute(
        "SELECT strftime('%Y-%m', expense_date) AS month, SUM(amount) AS total "
        "FROM expenses WHERE user_id = ? AND type = 'expense' "
        "GROUP BY month ORDER BY month DESC LIMIT 6",
        (uid,),
    ).fetchall()
    trend = list(reversed(trend))

    income_this_month = monthly_income(plans, month) + current["extra"]

    return render_template(
        "summary.html",
        month=month,
        month_label=first.strftime("%B %Y"),
        prev_label=prev.strftime("%B %Y"),
        income=income_this_month,
        spent=current["spent"],
        savings=income_this_month - current["spent"],
        change=change,
        categories=categories,
        cat_labels=[c["category"] for c in categories],
        cat_values=[round(c["total"], 2) for c in categories],
        trend_labels=[t["month"] for t in trend],
        trend_values=[round(t["total"], 2) for t in trend],
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)