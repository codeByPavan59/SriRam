from flask import (
    Flask, request, redirect, url_for,
    render_template_string, flash, session, abort
)
from functools import wraps
import sqlite3
import math
import os

app = Flask(__name__)
app.secret_key = os.environ.get(
    "FLASK_SECRET_KEY", "change-this-secret-key"
)

DATABASE = "products.db"

# ==========================================
# DATABASE
# ==========================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def create_tables():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            grams REAL NOT NULL,
            price REAL NOT NULL,
            unit TEXT NOT NULL DEFAULT 'Pieces',
            quantity INTEGER NOT NULL DEFAULT 1,
            pieces_per_case INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Add the unit column to an older database if needed.
    columns = [
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(products)"
        ).fetchall()
    ]

    if "unit" not in columns:
        conn.execute("""
            ALTER TABLE products
            ADD COLUMN unit TEXT NOT NULL DEFAULT 'Pieces'
        """)

    if "quantity" not in columns:
        conn.execute("""
            ALTER TABLE products
            ADD COLUMN quantity INTEGER NOT NULL DEFAULT 1
        """)

    if "pieces_per_case" not in columns:
        conn.execute("""
            ALTER TABLE products
            ADD COLUMN pieces_per_case INTEGER NOT NULL DEFAULT 1
        """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS test_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id)
                REFERENCES products(id)
                ON DELETE CASCADE
        )
    """)

    conn.commit()
    conn.close()


# Create database tables when the application starts.
create_tables()


# ==========================================
# ROLE PROTECTION
# ==========================================

def require_role(role):
    def decorator(function):
        @wraps(function)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                abort(403)
            return function(*args, **kwargs)
        return wrapper
    return decorator


# ==========================================
# HTML DESIGN
# ==========================================

PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Product Management App</title>

<style>
* {
    box-sizing: border-box;
}

body {
    font-family: Arial, sans-serif;
    background: #eef2f7;
    margin: 0;
    padding: 15px;
    color: #222;
}

.container {
    max-width: 1000px;
    margin: auto;
    background: white;
    padding: 22px;
    border-radius: 15px;
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

.roles {
    display: flex;
    justify-content: center;
    gap: 20px;
    flex-wrap: wrap;
    margin: 35px 0;
}

.role {
    display: block;
    width: 230px;
    padding: 30px 15px;
    border-radius: 15px;
    text-align: center;
    text-decoration: none;
    color: white;
    font-size: 24px;
    font-weight: bold;
}

.role span {
    display: block;
    font-size: 55px;
    margin-bottom: 12px;
}

.editor-role {
    background: #1769d2;
}

.tester-role {
    background: #15965b;
}

label {
    display: block;
    font-weight: bold;
    margin-top: 12px;
}

input, select, textarea {
    width: 100%;
    padding: 12px;
    margin: 7px 0;
    border: 1px solid #ccc;
    border-radius: 7px;
    font-size: 15px;
}

textarea {
    min-height: 75px;
}

button, .btn {
    display: inline-block;
    padding: 10px 15px;
    border: none;
    border-radius: 7px;
    color: white;
    background: #1769d2;
    cursor: pointer;
    text-decoration: none;
    margin: 4px 2px;
    font-size: 14px;
}

.green {
    background: #15965b;
}

.red {
    background: #d83232;
}

.gray {
    background: #555;
}

.message {
    background: #e4f7e9;
    color: #17632f;
    padding: 12px;
    border-radius: 7px;
    margin-bottom: 15px;
}

.product-card {
    border: 1px solid #ddd;
    border-radius: 10px;
    padding: 15px;
    margin: 15px 0;
}

.product-card h3 {
    color: #183153;
    margin-top: 0;
}

.table-wrap {
    overflow-x: auto;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 18px;
}

th, td {
    padding: 11px;
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
    body {
        padding: 8px;
    }

    .container {
        padding: 13px;
    }

    .role {
        width: 100%;
    }

    th, td {
        padding: 7px;
        font-size: 12px;
    }
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


{% if page == "home" %}

    <h1>📦 PRODUCT MANAGEMENT</h1>
    <p class="subtitle">Choose your workspace</p>

    <div class="roles">
        <a class="role editor-role"
           href="{{ url_for('choose_role', role='editor') }}">
            <span>📝</span>
            EDITOR
        </a>

        <a class="role tester-role"
           href="{{ url_for('choose_role', role='tester') }}">
            <span>🧪</span>
            TESTER
        </a>
    </div>


{% elif page == "editor" %}

    <h1>📝 EDITOR PANEL</h1>

    <a class="btn gray" href="{{ url_for('home') }}">Home</a>

    <h2>
        {% if edit_product %}
            Edit Product
        {% else %}
            Add New Product
        {% endif %}
    </h2>

    <form method="POST"
          action="{% if edit_product %}
              {{ url_for('edit_product',
                         product_id=edit_product.id) }}
          {% else %}
              {{ url_for('add_product') }}
          {% endif %}">

        <label>Product Name</label>
        <input type="text"
               name="name"
               maxlength="120"
               required
               placeholder="Enter product name"
               value="{{ edit_product.name if edit_product else '' }}">

        <label>Grams</label>
        <input type="number"
               name="grams"
               step="any"
               min="0.01"
               required
               placeholder="Enter grams"
               value="{{ edit_product.grams if edit_product else '' }}">

        <label>Price (₹)</label>
        <input type="number"
               name="price"
               step="0.01"
               min="0"
               required
               placeholder="Enter price"
               value="{{ edit_product.price if edit_product else '' }}">

        <label>Unit Type</label>
        <select name="unit" required>
            <option value="Pieces"
                {% if edit_product and edit_product.unit == 'Pieces' %}
                    selected
                {% endif %}>
                Pieces
            </option>

            <option value="Cases"
                {% if edit_product and edit_product.unit == 'Cases' %}
                    selected
                {% endif %}>
                Cases
            </option>
        </select>

        <label id="quantity-label">Number of Pieces</label>
        <input type="number"
               name="quantity"
               id="quantity"
               min="1"
               step="1"
               required
               value="{{ edit_product.quantity if edit_product else 1 }}"
               placeholder="Enter quantity">

        <div id="pieces-per-case-group" style="display:none">
            <label>How many pieces are there in each case?</label>
            <input type="number"
                   name="pieces_per_case"
                   id="pieces_per_case"
                   min="1"
                   step="1"
                   value="{{ edit_product.pieces_per_case if edit_product else 1 }}"
                   placeholder="Enter pieces per case">
        </div>

        <button type="submit">
            {% if edit_product %}
                Update Product
            {% else %}
                Add Product
            {% endif %}
        </button>

        {% if edit_product %}
            <a class="btn gray"
               href="{{ url_for('editor') }}">Cancel</a>
        {% endif %}
    </form>


    <h2>All Products</h2>

    <form method="GET" action="{{ url_for('editor') }}">
        <input type="text"
               name="q"
               value="{{ q }}"
               placeholder="Search product name">
        <button type="submit">Search</button>
        <a class="btn gray" href="{{ url_for('editor') }}">Clear</a>
    </form>

    <div class="table-wrap">
    <table>
        <tr>
            <th>ID</th>
            <th>Product Name</th>
            <th>Grams</th>
            <th>Price</th>
            <th>Unit</th>
            <th>Quantity</th>
            <th>Total Pieces</th>
            <th>Actions</th>
        </tr>

        {% for p in products %}
        <tr>
            <td>{{ p.id }}</td>
            <td>{{ p.name }}</td>
            <td>{{ p.grams }}</td>
            <td>₹{{ "%.2f"|format(p.price) }}</td>
            <td>{{ p.unit }}</td>
            <td>
                {% if p.unit == 'Cases' %}
                    {{ p.quantity }} Cases × {{ p.pieces_per_case }} pieces
                {% else %}
                    {{ p.quantity }} Pieces
                {% endif %}
            </td>
            <td>
                {% if p.unit == 'Cases' %}
                    {{ p.quantity * p.pieces_per_case }}
                {% else %}
                    {{ p.quantity }}
                {% endif %}
            </td>
            <td>
                <a class="btn green"
                   href="{{ url_for('edit_product',
                                    product_id=p.id) }}">Edit</a>

                <form method="POST"
                      action="{{ url_for('delete_product',
                                         product_id=p.id) }}"
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
        <input type="text"
               name="q"
               value="{{ q }}"
               placeholder="Search product name">
        <button type="submit">Search</button>
        <a class="btn gray" href="{{ url_for('tester') }}">Clear</a>
    </form>

    {% for p in products %}
    <div class="product-card">

        <h3>{{ p.name }}</h3>
        <p><b>Product ID:</b> {{ p.id }}</p>
        <p><b>Grams:</b> {{ p.grams }}</p>
        <p><b>Price:</b> ₹{{ "%.2f"|format(p.price) }}</p>
        <p><b>Unit:</b> {{ p.unit }}</p>
        {% if p.unit == 'Cases' %}
            <p><b>Cases:</b> {{ p.quantity }}</p>
            <p><b>Pieces in each case:</b> {{ p.pieces_per_case }}</p>
            <p><b>Total Pieces:</b> {{ p.quantity * p.pieces_per_case }}</p>
        {% else %}
            <p><b>Number of Pieces:</b> {{ p.quantity }}</p>
            <p><b>Total Pieces:</b> {{ p.quantity }}</p>
        {% endif %}

        <form method="POST"
              action="{{ url_for('save_test',
                                 product_id=p.id) }}">

            <label>Testing Result</label>
            <select name="status" required>
                <option value="Passed">Passed</option>
                <option value="Failed">Failed</option>
                <option value="Needs Review">Needs Review</option>
            </select>

            <label>Testing Notes</label>
            <textarea name="notes"
                      maxlength="1000"
                      placeholder="Write testing comments here"></textarea>

            <button class="green" type="submit">
                Save Test Result
            </button>
        </form>

    </div>
    {% endfor %}

    {% if not products %}
        <p class="empty">No products found.</p>
    {% endif %}

    <h2>Recent Testing Results</h2>

    <div class="table-wrap">
    <table>
        <tr>
            <th>Product</th>
            <th>Result</th>
            <th>Notes</th>
            <th>Date</th>
        </tr>

        {% for result in results %}
        <tr>
            <td>{{ result.product_name }}</td>
            <td>{{ result.status }}</td>
            <td>{{ result.notes or '-' }}</td>
            <td>{{ result.created_at }}</td>
        </tr>
        {% endfor %}
    </table>
    </div>

    {% if not results %}
        <p class="empty">No testing results yet.</p>
    {% endif %}

{% endif %}

</div>

<script>
function updateQuantityFields() {
    const unit = document.querySelector('select[name="unit"]');
    if (!unit) return;

    const casesSelected = unit.value === "Cases";
    document.getElementById("quantity-label").textContent =
        casesSelected ? "Number of Cases" : "Number of Pieces";
    document.getElementById("pieces-per-case-group").style.display =
        casesSelected ? "block" : "none";

    const piecesPerCase = document.getElementById("pieces_per_case");
    piecesPerCase.required = casesSelected;
}
document.addEventListener("DOMContentLoaded", function () {
    const unit = document.querySelector('select[name="unit"]');
    if (unit) {
        unit.addEventListener("change", updateQuantityFields);
        updateQuantityFields();
    }
});
</script>
</body>
</html>
"""


# ==========================================
# HOME AND ROLE SELECTION
# ==========================================

@app.route("/")
def home():
    session.pop("role", None)
    return render_template_string(PAGE, page="home")


@app.route("/choose/<role>")
def choose_role(role):
    if role not in ("editor", "tester"):
        abort(404)

    session["role"] = role

    if role == "editor":
        return redirect(url_for("editor"))

    return redirect(url_for("tester"))


# ==========================================
# VALIDATE PRODUCT DETAILS
# ==========================================

def get_product_details():
    name = request.form.get("name", "").strip()
    unit = request.form.get("unit", "")

    try:
        grams = float(request.form.get("grams", ""))
        price = float(request.form.get("price", ""))
        quantity = int(request.form.get("quantity", ""))
        pieces_per_case = (
            int(request.form.get("pieces_per_case", "1"))
            if unit == "Cases" else 1
        )

        if (
            not name
            or len(name) > 120
            or not math.isfinite(grams)
            or not math.isfinite(price)
            or grams <= 0
            or price < 0
            or quantity < 1
            or pieces_per_case < 1
            or unit not in ("Cases", "Pieces")
        ):
            raise ValueError

    except (ValueError, TypeError):
        return None

    return name, grams, price, unit, quantity, pieces_per_case


# ==========================================
# EDITOR PAGE
# ==========================================

@app.route("/editor")
@require_role("editor")
def editor():
    q = request.args.get("q", "").strip()

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE name LIKE ?
        ORDER BY id DESC
    """, ("%" + q + "%",)).fetchall()

    conn.close()

    return render_template_string(
        PAGE,
        page="editor",
        products=products,
        q=q,
        edit_product=None
    )


# ==========================================
# ADD PRODUCT
# ==========================================

@app.route("/add", methods=["POST"])
@require_role("editor")
def add_product():
    details = get_product_details()

    if details is None:
        flash("Please enter valid product details.")
        return redirect(url_for("editor"))

    conn = get_db()

    conn.execute("""
        INSERT INTO products
            (name, grams, price, unit, quantity, pieces_per_case)
        VALUES (?, ?, ?, ?, ?, ?)
    """, details)

    conn.commit()
    conn.close()

    flash("Product added successfully!")
    return redirect(url_for("editor"))


# ==========================================
# EDIT PRODUCT
# ==========================================

@app.route("/edit/<int:product_id>", methods=["GET", "POST"])
@require_role("editor")
def edit_product(product_id):
    conn = get_db()

    if request.method == "POST":
        details = get_product_details()

        if details is None:
            conn.close()
            flash("Please enter valid product details.")
            return redirect(url_for("editor"))

        cursor = conn.execute("""
            UPDATE products
            SET name = ?, grams = ?, price = ?, unit = ?,
                quantity = ?, pieces_per_case = ?
            WHERE id = ?
        """, (*details, product_id))

        conn.commit()
        conn.close()

        if cursor.rowcount == 0:
            flash("Product not found.")
        else:
            flash("Product updated successfully!")

        return redirect(url_for("editor"))

    product = conn.execute(
        "SELECT * FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    products = conn.execute(
        "SELECT * FROM products ORDER BY id DESC"
    ).fetchall()

    conn.close()

    if product is None:
        flash("Product not found.")
        return redirect(url_for("editor"))

    return render_template_string(
        PAGE,
        page="editor",
        products=products,
        q="",
        edit_product=product
    )


# ==========================================
# DELETE PRODUCT
# ==========================================

@app.route("/delete/<int:product_id>", methods=["POST"])
@require_role("editor")
def delete_product(product_id):
    conn = get_db()

    cursor = conn.execute(
        "DELETE FROM products WHERE id = ?",
        (product_id,)
    )

    conn.commit()
    conn.close()

    if cursor.rowcount == 0:
        flash("Product not found.")
    else:
        flash("Product deleted successfully!")

    return redirect(url_for("editor"))


# ==========================================
# TESTER PAGE
# ==========================================

@app.route("/tester")
@require_role("tester")
def tester():
    q = request.args.get("q", "").strip()

    conn = get_db()

    products = conn.execute("""
        SELECT * FROM products
        WHERE name LIKE ?
        ORDER BY id DESC
    """, ("%" + q + "%",)).fetchall()

    results = conn.execute("""
        SELECT
            test_results.status,
            test_results.notes,
            test_results.created_at,
            products.name AS product_name
        FROM test_results
        JOIN products
            ON products.id = test_results.product_id
        ORDER BY test_results.id DESC
        LIMIT 30
    """).fetchall()

    conn.close()

    return render_template_string(
        PAGE,
        page="tester",
        products=products,
        results=results,
        q=q
    )


# ==========================================
# SAVE TEST RESULT
# ==========================================

@app.route("/test/<int:product_id>", methods=["POST"])
@require_role("tester")
def save_test(product_id):
    status = request.form.get("status", "")
    notes = request.form.get("notes", "").strip()

    allowed_statuses = (
        "Passed",
        "Failed",
        "Needs Review"
    )

    if status not in allowed_statuses or len(notes) > 1000:
        flash("Please enter a valid testing result.")
        return redirect(url_for("tester"))

    conn = get_db()

    product = conn.execute(
        "SELECT id FROM products WHERE id = ?",
        (product_id,)
    ).fetchone()

    if product is None:
        conn.close()
        flash("Product not found.")
        return redirect(url_for("tester"))

    conn.execute("""
        INSERT INTO test_results (product_id, status, notes)
        VALUES (?, ?, ?)
    """, (product_id, status, notes))

    conn.commit()
    conn.close()

    flash("Testing result saved successfully!")
    return redirect(url_for("tester"))


# ==========================================
# ERROR PAGE
# ==========================================

@app.errorhandler(403)
def forbidden(error):
    return (
        "Access denied. Return to the home page "
        "and select your workspace.",
        403
    )


# ==========================================
# RUN APPLICATION
# ==========================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)