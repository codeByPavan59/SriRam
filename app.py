
import os
import math
import sqlite3
from datetime import date

from functools import wraps
from flask import (
    Flask, request, redirect, url_for,
    render_template_string, flash, session, abort
)
from werkzeug.security import generate_password_hash, check_password_hash


# ==================================================
# APP CONFIGURATION
# ==================================================

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY",
    "change-this-secret-key-before-sharing"
)

DATABASE = "product_manager.db"


# ==================================================
# DATABASE
# ==================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            grams REAL NOT NULL,
            price REAL NOT NULL,
            unit_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            pieces_per_case INTEGER NOT NULL DEFAULT 1,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES saved_files(id)
                ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(file_id) REFERENCES saved_files(id)
                ON DELETE CASCADE,
            FOREIGN KEY(product_id) REFERENCES products(id)
                ON DELETE CASCADE
        )
    """)

    product_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(products)").fetchall()
    }
    if "order_date" not in product_columns:
        conn.execute(
            "ALTER TABLE products ADD COLUMN order_date TEXT"
        )
        conn.execute("""
            UPDATE products
            SET order_date = substr(date_added, 1, 10)
            WHERE order_date IS NULL
        """)

    conn.commit()
    conn.close()


create_tables()


# ==================================================
# HELPERS
# ==================================================

def active_file_required(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        if not session.get("file_id"):
            return redirect(url_for("file_home"))
        return function(*args, **kwargs)
    return wrapper


def require_role(role):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                abort(403)
            return function(*args, **kwargs)
        return wrapper
    return decorator


def get_product_details():
    name = request.form.get("name", "").strip()
    unit_type = request.form.get("unit_type", "")
    order_date = request.form.get("order_date", "").strip()

    try:
        grams = float(request.form.get("grams", ""))
        price = float(request.form.get("price", ""))
        quantity = int(request.form.get("quantity", ""))
        pieces_per_case = int(
            request.form.get("pieces_per_case", "1")
        )
        date.fromisoformat(order_date)

        if (
            not name
            or len(name) > 120
            or not math.isfinite(grams)
            or not math.isfinite(price)
            or grams <= 0
            or price < 0
            or quantity <= 0
            or pieces_per_case <= 0
            or unit_type not in ("Cases", "Pieces")
        ):
            raise ValueError

        if unit_type == "Pieces":
            pieces_per_case = 1

    except (ValueError, TypeError, OverflowError):
        return None

    return (
        name, grams, price, unit_type,
        quantity, pieces_per_case, order_date
    )


# ==================================================
# HTML PAGE
# ==================================================

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>Product Management</title>

<style>
* { box-sizing: border-box; }

body {
    font-family: Arial, sans-serif;
    background: #eef2f7;
    margin: 0;
    padding: 12px;
    color: #222;
}

.container {
    max-width: 1000px;
    margin: auto;
    background: white;
    padding: 22px;
    border-radius: 14px;
    box-shadow: 0 3px 15px #0002;
}

h1, h2 {
    text-align: center;
    color: #183153;
}

.subtitle {
    text-align: center;
    color: #666;
}

label {
    display: block;
    font-weight: bold;
    margin-top: 14px;
}

input, select, textarea {
    width: 100%;
    padding: 14px;
    margin: 7px 0;
    border: 1px solid #ccc;
    border-radius: 8px;
    font-size: 16px;
}

textarea { min-height: 80px; }

button, .btn {
    display: inline-block;
    padding: 12px 17px;
    margin: 4px 2px;
    border: none;
    border-radius: 7px;
    background: #1769d2;
    color: white;
    text-decoration: none;
    cursor: pointer;
    font-size: 15px;
}

.green { background: #15965b; }
.red { background: #d83232; }
.gray { background: #555; }

.message {
    padding: 12px;
    margin: 10px 0;
    background: #e4f7e9;
    color: #17632f;
    border-radius: 7px;
}

.roles {
    display: flex;
    gap: 20px;
    justify-content: center;
    flex-wrap: wrap;
    margin: 35px 0;
}

.role {
    display: block;
    width: 260px;
    padding: 30px 15px;
    border-radius: 15px;
    text-align: center;
    text-decoration: none;
    color: white;
    font-size: 25px;
    font-weight: bold;
}

.role span {
    display: block;
    font-size: 55px;
    margin-bottom: 12px;
}

.editor-role { background: #1769d2; }
.tester-role { background: #15965b; }

.file-card, .product-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 15px;
    margin: 15px 0;
}

.file-card h3, .product-card h3 {
    color: #183153;
}

.unit-box {
    display: flex;
    gap: 12px;
}

.unit-option {
    flex: 1;
    border: 2px solid #1769d2;
    border-radius: 9px;
    padding: 13px;
    text-align: center;
    background: #f7faff;
}

.unit-option input {
    width: auto;
}

.quantity-box {
    background: #f3f6fa;
    padding: 15px;
    margin-top: 12px;
    border-radius: 10px;
}

.table-wrap { overflow-x: auto; }

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 18px;
}

th, td {
    padding: 10px;
    border: 1px solid #ddd;
    text-align: center;
}

th {
    background: #183153;
    color: white;
}

.empty {
    text-align: center;
    color: #777;
    padding: 20px;
}

@media(max-width: 600px) {
    .container { padding: 13px; }
    .role { width: 100%; }
    .unit-box { flex-direction: column; }
    th, td { padding: 7px; font-size: 12px; }
}
</style>
</head>

<body>
<div class="container">

{% with messages = get_flashed_messages() %}
    {% for message in messages %}
        <div class="message">{{ message }}</div>
    {% endfor %}
{% endwith %}


{% if page == "files" %}

    <h1>📁 PRODUCT MANAGEMENT</h1>
    <p class="subtitle">Create a new file or open a saved file</p>

    <h2>Create New File</h2>

    <form method="POST" action="{{ url_for('create_file') }}">
        <label>File Name</label>
        <input name="file_name" required maxlength="100"
               placeholder="Enter file name">

        <label>Username</label>
        <input name="username" required maxlength="80"
               placeholder="Enter username">

        <label>File Password</label>
        <input type="password" name="password"
               required minlength="8"
               placeholder="Create a password (at least 8 characters)">

        <button type="submit">Create File</button>
    </form>

    <hr>

    <h2>Saved Files</h2>

    {% for f in files %}
        <div class="file-card">
            <h3>📁 {{ f.file_name }}</h3>
            <p>Created by: {{ f.username }}</p>
            <p>Created: {{ f.created_at }}</p>
            <a class="btn green"
               href="{{ url_for('open_file', file_id=f.id) }}">
                Open File
            </a>
        </div>
    {% else %}
        <p class="empty">No saved files yet.</p>
    {% endfor %}


{% elif page == "open_file" %}

    <h1>🔐 Open Saved File</h1>
    <h2>{{ file.file_name }}</h2>
    <p class="subtitle">Enter the file password to continue.</p>

    <form method="POST">
        <label>File Password</label>
        <input type="password" name="password"
               required placeholder="Enter file password">
        <button type="submit">Open File</button>
    </form>

    <a class="btn gray" href="{{ url_for('file_home') }}">
        Back to Saved Files
    </a>


{% elif page == "home" %}

    <h1>📦 PRODUCT MANAGEMENT</h1>
    <p class="subtitle">File: {{ file_name }}</p>

    <div class="roles">
        <a class="role editor-role"
           href="{{ url_for('choose_role', role='editor') }}">
            <span>📝</span>
            EDITOR
            <small>Add, edit, delete and search products</small>
        </a>

        <a class="role tester-role"
           href="{{ url_for('choose_role', role='tester') }}">
            <span>🧪</span>
            TESTER
            <small>View products and record testing results</small>
        </a>
    </div>

    <a class="btn gray" href="{{ url_for('file_home') }}">
        Back to Saved Files
    </a>


{% elif page == "editor" %}

    <h1>📝 EDITOR PANEL</h1>
    <a class="btn gray" href="{{ url_for('home') }}">Home</a>

    <h2>{{ "Edit Product" if edit_product else "Add New Product" }}</h2>

    <form method="POST"
          action="{% if edit_product %}
              {{ url_for('edit_product', product_id=edit_product.id) }}
          {% else %}
              {{ url_for('add_product') }}
          {% endif %}">

        <label>Product Name</label>
        <input name="name" required maxlength="120"
               placeholder="Enter product name"
               value="{{ edit_product.name if edit_product else '' }}">

        <label>Grams</label>
        <input type="number" name="grams"
               step="any" min="0.01" required
               placeholder="Enter grams"
               value="{{ edit_product.grams if edit_product else '' }}">

        <label>Price (₹)</label>
        <input type="number" name="price"
               step="0.01" min="0" required
               placeholder="Enter price"
               value="{{ edit_product.price if edit_product else '' }}">

        <label>Order Date</label>
        <input type="date" name="order_date" required
               value="{{ edit_product.order_date if edit_product else '' }}">

        <div class="quantity-box">
            <h3>Unit Type</h3>

            <div class="unit-box">
                <label class="unit-option">
                    <input type="radio" name="unit_type"
                           value="Cases" required
                           {% if not edit_product or edit_product.unit_type == 'Cases' %}
                           checked{% endif %}>
                    📦 Cases
                </label>

                <label class="unit-option">
                    <input type="radio" name="unit_type"
                           value="Pieces" required
                           {% if edit_product and edit_product.unit_type == 'Pieces' %}
                           checked{% endif %}>
                    🧩 Pieces
                </label>
            </div>

            <label id="quantity-label">Number of Cases</label>
            <input type="number" name="quantity" id="quantity"
                   min="1" step="1" required
                   value="{{ edit_product.quantity if edit_product else 1 }}">

            <div id="pieces-case-box">
                <label>How many pieces are there in each case?</label>
                <input type="number" name="pieces_per_case"
                       id="pieces_per_case"
                       min="1" step="1"
                       value="{{ edit_product.pieces_per_case if edit_product else 1 }}">
            </div>
        </div>

        <button type="submit">
            {{ "Update Product" if edit_product else "Add Product" }}
        </button>

        {% if edit_product %}
            <a class="btn gray" href="{{ url_for('editor') }}">Cancel</a>
        {% endif %}
    </form>

    <h2>All Products</h2>

    <form method="GET" action="{{ url_for('editor') }}">
        <input name="q" value="{{ q }}"
               placeholder="Search product name">
        <button type="submit">Search</button>
        <a class="btn gray" href="{{ url_for('editor') }}">Clear</a>
    </form>

    <div class="table-wrap">
    <table>
        <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Order Date</th>
            <th>Grams</th>
            <th>Price</th>
            <th>Unit</th>
            <th>Quantity</th>
            <th>Pieces/Case</th>
            <th>Actions</th>
        </tr>

        {% for p in products %}
        <tr>
            <td>{{ p.id }}</td>
            <td>{{ p.name }}</td>
            <td>{{ p.order_date or '-' }}</td>
            <td>{{ p.grams }}</td>
            <td>₹{{ "%.2f"|format(p.price) }}</td>
            <td>{{ p.unit_type }}</td>
            <td>{{ p.quantity }}</td>
            <td>{{ p.pieces_per_case if p.unit_type == 'Cases' else '-' }}</td>
            <td>
                <a class="btn green"
                   href="{{ url_for('edit_product', product_id=p.id) }}">
                    Edit
                </a>

                <form method="POST"
                      action="{{ url_for('delete_product', product_id=p.id) }}"
                      style="display:inline"
                      onsubmit="return confirm('Delete this product?')">
                    <button class="red" type="submit">Delete</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    </div>

    {% if not products %}
        <p class="empty">No products found.</p>
    {% endif %}


{% elif page == "tester" %}

    <h1>🧪 TESTER PANEL</h1>
    <a class="btn gray" href="{{ url_for('home') }}">Home</a>

    <h2>Available Products</h2>

    <form method="GET" action="{{ url_for('tester') }}">
        <input name="q" value="{{ q }}"
               placeholder="Search product name">
        <button type="submit">Search</button>
        <a class="btn gray" href="{{ url_for('tester') }}">Clear</a>
    </form>

    {% for p in products %}
    <div class="product-card">
        <h3>{{ p.name }}</h3>
        <p><b>Order Date:</b> {{ p.order_date or '-' }}</p>
        <p><b>Grams:</b> {{ p.grams }}</p>
        <p><b>Price:</b> ₹{{ "%.2f"|format(p.price) }}</p>
        <p><b>Unit Type:</b> {{ p.unit_type }}</p>
        <p><b>Quantity:</b> {{ p.quantity }}</p>

        {% if p.unit_type == "Cases" %}
            <p><b>Pieces in each case:</b> {{ p.pieces_per_case }}</p>
            <p><b>Total pieces:</b> {{ p.quantity * p.pieces_per_case }}</p>
        {% endif %}

        <form method="POST"
              action="{{ url_for('save_test', product_id=p.id) }}">
            <label>Testing Result</label>
            <select name="status" required>
                <option value="Passed">Passed</option>
                <option value="Failed">Failed</option>
                <option value="Needs Review">Needs Review</option>
            </select>

            <label>Testing Notes</label>
            <textarea name="notes" maxlength="1000"
                      placeholder="Enter testing notes"></textarea>

            <button class="green" type="submit">
                Save Test Result
            </button>
        </form>
    </div>
    {% else %}
        <p class="empty">No products available.</p>
    {% endfor %}

    <h2>Recent Testing Results</h2>

    <div class="table-wrap">
    <table>
        <tr>
            <th>Product</th>
            <th>Result</th>
            <th>Notes</th>
            <th>Date</th>
        </tr>
        {% for r in results %}
        <tr>
            <td>{{ r.product_name }}</td>
            <td>{{ r.status }}</td>
            <td>{{ r.notes or '-' }}</td>
            <td>{{ r.created_at }}</td>
        </tr>
        {% else %}
        <tr><td colspan="4">No testing results yet.</td></tr>
        {% endfor %}
    </table>
    </div>

{% endif %}

</div>

<script>
function updateQuantityFields() {
    const selected = document.querySelector(
        'input[name="unit_type"]:checked'
    );

    const label = document.getElementById("quantity-label");
    const caseBox = document.getElementById("pieces-case-box");
    const piecesInput = document.getElementById("pieces_per_case");

    if (!selected || !label || !caseBox || !piecesInput) {
        return;
    }

    if (selected.value === "Cases") {
        label.textContent = "Number of Cases";
        caseBox.style.display = "block";
        piecesInput.required = true;
    } else {
        label.textContent = "Number of Pieces";
        caseBox.style.display = "none";
        piecesInput.required = false;
    }
}

document.querySelectorAll('input[name="unit_type"]').forEach(
    function (radio) {
        radio.addEventListener("change", updateQuantityFields);
    }
);

updateQuantityFields();
</script>

</body>
</html>
"""


# ==================================================
# FILE HOME
# ==================================================

@app.route("/")
def file_home():
    session.clear()

    conn = get_db()
    files = conn.execute("""
        SELECT id, file_name, username, created_at
        FROM saved_files
        ORDER BY id DESC
    """).fetchall()
    conn.close()

    return render_template_string(
        PAGE,
        page="files",
        files=files
    )


# ==================================================
# CREATE FILE
# ==================================================

@app.route("/create-file", methods=["POST"])
def create_file():
    file_name = request.form.get("file_name", "").strip()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if (
        not file_name
        or len(file_name) > 100
        or not username
        or len(username) > 80
        or len(password) < 8
    ):
        flash("Enter valid details. Password must have at least 8 characters.")
        return redirect(url_for("file_home"))

    conn = get_db()

    try:
        conn.execute("""
            INSERT INTO saved_files
            (file_name, username, password_hash)
            VALUES (?, ?, ?)
        """, (
            file_name,
            username,
            generate_password_hash(password)
        ))
        conn.commit()

        file_id = conn.execute(
            "SELECT id FROM saved_files WHERE file_name = ?",
            (file_name,)
        ).fetchone()["id"]

    except sqlite3.IntegrityError:
        conn.close()
        flash("A file with this name already exists.")
        return redirect(url_for("file_home"))

    conn.close()

    session.clear()
    session["file_id"] = file_id
    session["role"] = None

    flash("File created successfully!")
    return redirect(url_for("home"))


# ==================================================
# OPEN SAVED FILE
# ==================================================

@app.route("/open-file/<int:file_id>", methods=["GET", "POST"])
def open_file(file_id):
    conn = get_db()
    saved_file = conn.execute(
        "SELECT * FROM saved_files WHERE id = ?",
        (file_id,)
    ).fetchone()
    conn.close()

    if saved_file is None:
        flash("Saved file not found.")
        return redirect(url_for("file_home"))

    if request.method == "POST":
        password = request.form.get("password", "")

        if check_password_hash(saved_file["password_hash"], password):
            session.clear()
            session["file_id"] = file_id
            session["role"] = None
            flash("File opened successfully!")
            return redirect(url_for("home"))

        flash("Incorrect file password.")

    return render_template_string(
        PAGE,
        page="open_file",
        file=saved_file
    )


# ==================================================
# MAIN HOME SCREEN
# ==================================================

@app.route("/home")
@active_file_required
def home():
    conn = get_db()
    saved_file = conn.execute(
        "SELECT file_name FROM saved_files WHERE id = ?",
        (session["file_id"],)
    ).fetchone()
    conn.close()

    if saved_file is None:
        session.clear()
        return redirect(url_for("file_home"))

    return render_template_string(
        PAGE,
        page="home",
        file_name=saved_file["file_name"]
    )


# ==================================================
# SELECT EDITOR OR TESTER
# ==================================================

@app.route("/choose/<role>")
@active_file_required
def choose_role(role):
    if role not in ("editor", "tester"):
        abort(404)

    session["role"] = role

    if role == "editor":
        return redirect(url_for("editor"))

    return redirect(url_for("tester"))


# ==================================================
# EDITOR
# ==================================================

@app.route("/editor")
@active_file_required
@require_role("editor")
def editor():
    q = request.args.get("q", "").strip()

    conn = get_db()
    products = conn.execute("""
        SELECT * FROM products
        WHERE file_id = ? AND name LIKE ?
        ORDER BY id DESC
    """, (session["file_id"], "%" + q + "%")).fetchall()
    conn.close()

    return render_template_string(
        PAGE,
        page="editor",
        products=products,
        q=q,
        edit_product=None
    )


# ==================================================
# ADD PRODUCT
# ==================================================

@app.route("/add", methods=["POST"])
@active_file_required
@require_role("editor")
def add_product():
    details = get_product_details()

    if details is None:
        flash("Please enter valid product details.")
        return redirect(url_for("editor"))

    conn = get_db()
    conn.execute("""
        INSERT INTO products
        (file_id, name, grams, price, unit_type, quantity,
         pieces_per_case, order_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (session["file_id"], *details))

    conn.commit()
    conn.close()

    flash("Product added successfully!")
    return redirect(url_for("editor"))


# ==================================================
# EDIT PRODUCT
# ==================================================

@app.route("/edit/<int:product_id>", methods=["GET", "POST"])
@active_file_required
@require_role("editor")
def edit_product(product_id):
    conn = get_db()

    product = conn.execute("""
        SELECT * FROM products
        WHERE id = ? AND file_id = ?
    """, (product_id, session["file_id"])).fetchone()

    if product is None:
        conn.close()
        flash("Product not found.")
        return redirect(url_for("editor"))

    if request.method == "POST":
        details = get_product_details()

        if details is None:
            conn.close()
            flash("Please enter valid product details.")
            return redirect(url_for("editor"))

        conn.execute("""
            UPDATE products
            SET name = ?,
                grams = ?,
                price = ?,
                unit_type = ?,
                quantity = ?,
                pieces_per_case = ?,
                order_date = ?,
                last_updated = CURRENT_TIMESTAMP
            WHERE id = ? AND file_id = ?
        """, (*details, product_id, session["file_id"]))

        conn.commit()
        conn.close()

        flash("Product updated successfully!")
        return redirect(url_for("editor"))

    products = conn.execute("""
        SELECT * FROM products
        WHERE file_id = ?
        ORDER BY id DESC
    """, (session["file_id"],)).fetchall()

    conn.close()

    return render_template_string(
        PAGE,
        page="editor",
        products=products,
        q="",
        edit_product=product
    )


# ==================================================
# DELETE PRODUCT
# ==================================================

@app.route("/delete/<int:product_id>", methods=["POST"])
@active_file_required
@require_role("editor")
def delete_product(product_id):
    conn = get_db()

    cursor = conn.execute("""
        DELETE FROM products
        WHERE id = ? AND file_id = ?
    """, (product_id, session["file_id"]))

    conn.commit()
    conn.close()

    if cursor.rowcount:
        flash("Product deleted successfully!")
    else:
        flash("Product not found.")

    return redirect(url_for("editor"))


# ==================================================
# TESTER
# ==================================================

@app.route("/tester")
@active_file_required
@require_role("tester")
def tester():
    q = request.args.get("q", "").strip()

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE file_id = ? AND name LIKE ?
        ORDER BY id DESC
    """, (session["file_id"], "%" + q + "%")).fetchall()

    results = conn.execute("""
        SELECT
            test_results.status,
            test_results.notes,
            test_results.created_at,
            products.name AS product_name
        FROM test_results
        JOIN products ON products.id = test_results.product_id
        WHERE test_results.file_id = ?
        ORDER BY test_results.id DESC
        LIMIT 30
    """, (session["file_id"],)).fetchall()

    conn.close()

    return render_template_string(
        PAGE,
        page="tester",
        products=products,
        results=results,
        q=q
    )


# ==================================================
# SAVE TEST RESULT
# ==================================================

@app.route("/test/<int:product_id>", methods=["POST"])
@active_file_required
@require_role("tester")
def save_test(product_id):
    status = request.form.get("status", "")
    notes = request.form.get("notes", "").strip()

    allowed = ("Passed", "Failed", "Needs Review")

    if status not in allowed or len(notes) > 1000:
        flash("Please enter a valid testing result.")
        return redirect(url_for("tester"))

    conn = get_db()

    product = conn.execute("""
        SELECT id FROM products
        WHERE id = ? AND file_id = ?
    """, (product_id, session["file_id"])).fetchone()

    if product is None:
        conn.close()
        flash("Product not found.")
        return redirect(url_for("tester"))

    conn.execute("""
        INSERT INTO test_results
        (file_id, product_id, status, notes)
        VALUES (?, ?, ?, ?)
    """, (
        session["file_id"],
        product_id,
        status,
        notes
    ))

    conn.commit()
    conn.close()

    flash("Testing result saved successfully!")
    return redirect(url_for("tester"))


# ==================================================
# LOGOUT / CLOSE CURRENT FILE
# ==================================================

@app.route("/close-file")
def close_file():
    session.clear()
    return redirect(url_for("file_home"))


# ==================================================
# ERROR HANDLERS
# ==================================================

@app.errorhandler(403)
def forbidden(error):
    return (
        "<h1>403 - Access Denied</h1>"
        '<a href="/">Return to Saved Files</a>',
        403
    )


@app.errorhandler(404)
def not_found(error):
    return (
        "<h1>404 - Page Not Found</h1>"
        '<a href="/">Return to Saved Files</a>',
        404
    )


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
