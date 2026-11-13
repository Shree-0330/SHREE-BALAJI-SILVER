
import streamlit as st
import streamlit.components.v1 as components
import sqlite3
import pandas as pd
import os
import io
import html
import hashlib
import calendar

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

# ============================================================
# SHREE BALAJI SILVER
# ============================================================

st.set_page_config(
    page_title="SHREE BALAJI SILVER",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "database")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "sbs_billing.db")

SHOP_NAME = "SHREE BALAJI SILVER"
SHOP_ADDRESS = (
    "Old No. 48, Veerappan Street, "
    "1st Floor, in 3C Complex, Sowcarpet, "
    "Chennai - 600079"
)
SHOP_PHONE = "044-4277 6926, 4276 7395"
SHOP_CENTREX = "1000, 1999"

TRANSACTION_TYPES = [
    "Sales",
    "Receipt",
    "Sales Return",
    "Purchase",
    "Purchase Return",
    "Issue"
]

DEFAULT_MASTERS = {
    "Sundry Debtors": ["Cash Customer"],
    "Category": ["1LG", "2ARTICLE", "SILVER"],
    "Item": [
        "81 SOL PLAIN",
        "81 SOL ENG",
        "81 KOLHAPUR",
        "TANDA",
        "KAPS FANCY",
        "KADA PUNJABI",
        "KADA 81",
        "SALEM PAYAL 81"
    ]
}

# ============================================================
# DATABASE
# ============================================================

def get_db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def initialize_database():

    con = get_db()

    con.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    );

    CREATE TABLE IF NOT EXISTS customers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_number TEXT UNIQUE,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS masters(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        master_type TEXT,
        value TEXT,
        created_at TEXT,
        UNIQUE(master_type,value)
    );

    CREATE TABLE IF NOT EXISTS transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reference_number TEXT UNIQUE,
        transaction_type TEXT,
        operation TEXT,
        customer_number TEXT,
        customer_name TEXT,
        phone TEXT,
        customer_address TEXT,
        transaction_date TEXT,
        transaction_time TEXT,
        narration TEXT,
        gst_percent REAL DEFAULT 0,
        tax_type TEXT DEFAULT 'Local',
        sales_pure REAL DEFAULT 0,
        receipt_pure REAL DEFAULT 0,
        metal_due REAL DEFAULT 0,
        sales_mc REAL DEFAULT 0,
        receipt_mc REAL DEFAULT 0,
        amount_due REAL DEFAULT 0,
        subtotal REAL DEFAULT 0,
        cgst REAL DEFAULT 0,
        sgst REAL DEFAULT 0,
        igst REAL DEFAULT 0,
        total_tax REAL DEFAULT 0,
        grand_total REAL DEFAULT 0,
        created_at TEXT
    );

    CREATE TABLE IF NOT EXISTS transaction_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER,
        category TEXT,
        item_name TEXT,
        pieces INTEGER DEFAULT 0,
        gross_weight REAL DEFAULT 0,
        less_weight REAL DEFAULT 0,
        net_weight REAL DEFAULT 0,
        touch_percent REAL DEFAULT 0,
        fine_weight REAL DEFAULT 0,
        rate REAL DEFAULT 0,
        mc_amount REAL DEFAULT 0,
        receipt_issue TEXT DEFAULT 'Sales'
    );

    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaction_id INTEGER,
        action TEXT,
        description TEXT,
        created_at TEXT
    );
    """)

    # Exact text values preserve decimal zeros.
    additions = {
        "transaction_items": {
            "pieces_raw": "TEXT DEFAULT '0'",
            "gross_raw": "TEXT DEFAULT '0'",
            "less_raw": "TEXT DEFAULT '0'",
            "net_raw": "TEXT DEFAULT '0'",
            "touch_raw": "TEXT DEFAULT '0'",
            "pure_raw": "TEXT DEFAULT '0'",
            "rate_raw": "TEXT DEFAULT '0'",
            "mc_raw": "TEXT DEFAULT '0'",
            "weight_unit": "TEXT DEFAULT 'KG'",
            "rate_unit": "TEXT DEFAULT 'Per Gm'"
        }
    }

    for table, fields in additions.items():

        existing = {
            row["name"]
            for row in con.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()
        }

        for column, definition in fields.items():

            if column not in existing:

                con.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN {column} {definition}"
                )

    # Default login
    password = hashlib.sha256(
        os.getenv("SBS_ADMIN_PASSWORD", "admin123").encode()
    ).hexdigest()

    con.execute("""
        INSERT OR IGNORE INTO users(username,password)
        VALUES(?,?)
    """, (
        os.getenv("SBS_ADMIN_USER", "admin"),
        password
    ))

    for kind, values in DEFAULT_MASTERS.items():

        for value in values:

            con.execute("""
                INSERT OR IGNORE INTO masters(
                    master_type,value,created_at
                )
                VALUES(?,?,?)
            """, (
                kind,
                value,
                datetime.now().isoformat(timespec="seconds")
            ))

    con.commit()
    con.close()


initialize_database()

# ============================================================
# HELPERS
# ============================================================

def number(value):

    try:
        value = str(value).strip()

        if not value:
            return Decimal("0")

        return Decimal(value)

    except InvalidOperation:
        raise ValueError(
            f"Invalid number: {value}"
        )


def display_number(value):

    return str(value).strip() if str(value).strip() else "0"


def rupees(value):

    return "₹" + format(float(value or 0), ",.2f")


def format_weight(value):

    d = Decimal(str(value or 0))
    return format(d, "f")


def get_master(kind):

    con = get_db()

    rows = con.execute("""
        SELECT value FROM masters
        WHERE master_type=?
        ORDER BY value
    """, (kind,)).fetchall()

    con.close()

    return [r["value"] for r in rows]


def add_master(kind, value):

    value = str(value).strip()

    if not value:
        return False

    con = get_db()

    try:

        con.execute("""
            INSERT INTO masters(
                master_type,value,created_at
            )
            VALUES(?,?,?)
        """, (
            kind,
            value,
            datetime.now().isoformat(timespec="seconds")
        ))

        con.commit()
        return True

    except sqlite3.IntegrityError:
        return False

    finally:
        con.close()


def get_customers():

    con = get_db()

    df = pd.read_sql_query("""
        SELECT * FROM customers
        ORDER BY name
    """, con)

    con.close()

    return df


def get_all_transactions():

    con = get_db()

    df = pd.read_sql_query("""
        SELECT * FROM transactions
        ORDER BY id DESC
    """, con)

    con.close()

    return df


def get_bill(bill_number):

    con = get_db()

    row = con.execute("""
        SELECT * FROM transactions
        WHERE reference_number=?
    """, (bill_number,)).fetchone()

    con.close()

    return dict(row) if row else None


def get_items(transaction_id):

    con = get_db()

    df = pd.read_sql_query("""
        SELECT * FROM transaction_items
        WHERE transaction_id=?
        ORDER BY id
    """, con, params=(transaction_id,))

    con.close()

    return df


def generate_bill_number():

    today = date.today().strftime("%Y%m%d")
    prefix = f"SBS-{today}-"

    con = get_db()

    rows = con.execute("""
        SELECT reference_number FROM transactions
        WHERE reference_number LIKE ?
    """, (prefix + "%",)).fetchall()

    con.close()

    highest = 0

    for row in rows:

        try:
            highest = max(
                highest,
                int(row["reference_number"].split("-")[-1])
            )
        except Exception:
            pass

    return f"{prefix}{highest + 1:04d}"


# ============================================================
# CALCULATIONS
# USER ENTERED VALUES ARE USED AS THEY ARE.
# NO AUTOMATIC ITEM VALUES ARE INSERTED.
# ============================================================

def prepare_items(data):

    result = []

    for index, row in data.iterrows():

        name = str(row.get("Item Name", "") or "").strip()

        fields = [
            row.get("Gross Wt", ""),
            row.get("Net Wt", ""),
            row.get("Pure / Fine Wt", "")
        ]

        if not name and all(
            not str(x).strip() for x in fields
        ):
            continue

        if not name:
            raise ValueError(
                f"Row {index + 1}: Enter Item Name."
            )

        pieces_raw = display_number(row.get("Pcs", "0"))
        gross_raw = display_number(row.get("Gross Wt", "0"))
        less_raw = display_number(row.get("Less Wt", "0"))
        net_raw = display_number(row.get("Net Wt", "0"))
        touch_raw = display_number(row.get("Touch %", "0"))
        pure_raw = display_number(row.get("Pure / Fine Wt", "0"))
        rate_raw = display_number(row.get("Rate", "0"))
        weight_unit = str(row.get("Weight Unit", "KG") or "KG")
        rate_unit = str(row.get("Rate Unit", "Per Gm") or "Per Gm")
        if weight_unit not in ["Gm", "KG"]:
            weight_unit = "KG"
        if rate_unit not in ["Per Gm", "Per KG"]:
            rate_unit = "Per Gm"
        mc_raw = display_number(row.get("MC Amount", "0"))

        # Validate numeric entries without changing their text.
        pieces = number(pieces_raw)
        gross = number(gross_raw)
        less = number(less_raw)
        net = number(net_raw)
        touch = number(touch_raw)
        pure = number(pure_raw)
        rate = number(rate_raw)
        mc = number(mc_raw)

        if min(
            pieces, gross, less, net,
            touch, pure, rate, mc
        ) < 0:

            raise ValueError(
                f"Row {index + 1}: Negative numbers are not allowed."
            )

        category = str(
            row.get("Category", "") or ""
        ).strip()

        receipt_issue = str(
            row.get("Rec / Issue", "Sales") or "Sales"
        )

        if receipt_issue not in ["Sales", "Receipt"]:
            receipt_issue = "Sales"

        result.append({
            "category": category,
            "item_name": name,
            "pieces": int(pieces),
            "gross_weight": float(gross),
            "less_weight": float(less),
            "net_weight": float(net),
            "touch_percent": float(touch),
            "fine_weight": float(pure),
            "rate": float(rate),
            "mc_amount": float(mc),
            "receipt_issue": receipt_issue,

            # Exact text retained.
            "pieces_raw": pieces_raw,
            "gross_raw": gross_raw,
            "less_raw": less_raw,
            "net_raw": net_raw,
            "touch_raw": touch_raw,
            "pure_raw": pure_raw,
            "rate_raw": rate_raw,
            "mc_raw": mc_raw,
            "weight_unit": weight_unit,
            "rate_unit": rate_unit
        })

    if not result:
        raise ValueError("Please add at least one item.")

    return result


def calculate_summary(items):
    sales_pure = Decimal("0")
    receipt_pure = Decimal("0")

    sales_mc = Decimal("0")
    receipt_mc = Decimal("0")

    sales_value = Decimal("0")
    receipt_value = Decimal("0")

    for item in items:
        pure = number(item["pure_raw"])
        rate = number(item["rate_raw"])
        mc = number(item["mc_raw"])

        # Convert entered fine weight into grams.
        if item.get("weight_unit", "Gm") == "KG":
            pure_gm = pure * Decimal("1000")
        else:
            pure_gm = pure

        # Convert rate into price per gram.
        if item.get("rate_unit", "Per Gm") == "Per KG":
            rate_per_gm = rate / Decimal("1000")
        else:
            rate_per_gm = rate

        # Calculate item value using Fine Weight × Rate.
        item_value = pure_gm * rate_per_gm

        if item["receipt_issue"] == "Receipt":
            receipt_pure += pure_gm
            receipt_mc += mc
            receipt_value += item_value
        else:
            sales_pure += pure_gm
            sales_mc += mc
            sales_value += item_value

    metal_due = sales_pure - receipt_pure
    amount_due = (
        sales_value + sales_mc
        - receipt_value - receipt_mc
    )

    return {
        "sales_pure": sales_pure,
        "receipt_pure": receipt_pure,
        "metal_due": metal_due,
        "sales_mc": sales_mc,
        "receipt_mc": receipt_mc,
        "sales_value": sales_value,
        "receipt_value": receipt_value,
        "amount_due": amount_due
    }






def calculate_gst(amount, percent, tax_type):

    gst = amount * percent / Decimal("100")

    if tax_type == "Local":

        cgst = gst / Decimal("2")
        sgst = gst - cgst
        igst = Decimal("0")

    else:

        cgst = Decimal("0")
        sgst = Decimal("0")
        igst = gst

    return {
        "cgst": cgst,
        "sgst": sgst,
        "igst": igst,
        "total_tax": gst,
        "grand_total": amount + gst
    }


# ============================================================
# SAVE CUSTOMER
# ============================================================

def save_customer(number_value, name, phone, address):

    if not number_value.strip() or not name.strip():
        return

    con = get_db()

    con.execute("""
        INSERT INTO customers(
            customer_number,name,phone,address,created_at
        )
        VALUES(?,?,?,?,?)
        ON CONFLICT(customer_number)
        DO UPDATE SET
            name=excluded.name,
            phone=excluded.phone,
            address=excluded.address
    """, (
        number_value.strip(),
        name.strip(),
        phone.strip(),
        address.strip(),
        datetime.now().isoformat(timespec="seconds")
    ))

    con.commit()
    con.close()

    add_master("Sundry Debtors", name)


# ============================================================
# SAVE / CORRECT BILL
# ============================================================

def save_bill(payload, items):

    summary = calculate_summary(items)

    bill_number = payload["bill_number"]

    gst_percent = number(payload["gst_percent"])

    tax = calculate_gst(
        summary["amount_due"],
        gst_percent,
        payload["tax_type"]
    )

    now = datetime.now()

    con = get_db()

    try:

        existing = con.execute("""
            SELECT id FROM transactions
            WHERE reference_number=?
        """, (bill_number,)).fetchone()

        if payload["operation"] == "Correction":

            if not existing:
                raise ValueError("Bill not found.")

            tx_id = existing["id"]

            con.execute("""
                UPDATE transactions SET
                    transaction_type=?,
                    operation='Correction',
                    customer_number=?,
                    customer_name=?,
                    phone=?,
                    customer_address=?,
                    transaction_date=?,
                    transaction_time=?,
                    narration=?,
                    gst_percent=?,
                    tax_type=?,
                    sales_pure=?,
                    receipt_pure=?,
                    metal_due=?,
                    sales_mc=?,
                    receipt_mc=?,
                    amount_due=?,
                    subtotal=?,
                    cgst=?,
                    sgst=?,
                    igst=?,
                    total_tax=?,
                    grand_total=?,
                    created_at=?
                WHERE id=?
            """, (
                payload["transaction_type"],
                payload["customer_number"],
                payload["customer_name"],
                payload["phone"],
                payload["customer_address"],
                str(payload["transaction_date"]),
                str(payload["transaction_time"]),
                payload["narration"],
                float(gst_percent),
                payload["tax_type"],
                float(summary["sales_pure"]),
                float(summary["receipt_pure"]),
                float(summary["metal_due"]),
                float(summary["sales_mc"]),
                float(summary["receipt_mc"]),
                float(summary["amount_due"]),
                float(summary["amount_due"]),
                float(tax["cgst"]),
                float(tax["sgst"]),
                float(tax["igst"]),
                float(tax["total_tax"]),
                float(tax["grand_total"]),
                now.isoformat(timespec="seconds"),
                tx_id
            ))

            con.execute("""
                DELETE FROM transaction_items
                WHERE transaction_id=?
            """, (tx_id,))

            action = "CORRECTION"

        else:

            if existing:
                raise ValueError(
                    "Bill number already exists."
                )

            con.execute("""
                INSERT INTO transactions(
                    reference_number,
                    transaction_type,
                    operation,
                    customer_number,
                    customer_name,
                    phone,
                    customer_address,
                    transaction_date,
                    transaction_time,
                    narration,
                    gst_percent,
                    tax_type,
                    sales_pure,
                    receipt_pure,
                    metal_due,
                    sales_mc,
                    receipt_mc,
                    amount_due,
                    subtotal,
                    cgst,
                    sgst,
                    igst,
                    total_tax,
                    grand_total,
                    created_at
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                bill_number,
                payload["transaction_type"],
                "Addition",
                payload["customer_number"],
                payload["customer_name"],
                payload["phone"],
                payload["customer_address"],
                str(payload["transaction_date"]),
                str(payload["transaction_time"]),
                payload["narration"],
                float(gst_percent),
                payload["tax_type"],
                float(summary["sales_pure"]),
                float(summary["receipt_pure"]),
                float(summary["metal_due"]),
                float(summary["sales_mc"]),
                float(summary["receipt_mc"]),
                float(summary["amount_due"]),
                float(summary["amount_due"]),
                float(tax["cgst"]),
                float(tax["sgst"]),
                float(tax["igst"]),
                float(tax["total_tax"]),
                float(tax["grand_total"]),
                now.isoformat(timespec="seconds")
            ))

            tx_id = con.execute(
                "SELECT last_insert_rowid()"
            ).fetchone()[0]

            action = "ADDITION"

        for item in items:

            con.execute("""
                INSERT INTO transaction_items(
                    transaction_id,
                    category,
                    item_name,
                    pieces,
                    gross_weight,
                    less_weight,
                    net_weight,
                    touch_percent,
                    fine_weight,
                    rate,
                    mc_amount,
                    receipt_issue,
                    pieces_raw,
                    gross_raw,
                    less_raw,
                    net_raw,
                    touch_raw,
                    pure_raw,
                    rate_raw,
                    mc_raw,
                    weight_unit,
                    rate_unit
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                tx_id,
                item["category"],
                item["item_name"],
                item["pieces"],
                item["gross_weight"],
                item["less_weight"],
                item["net_weight"],
                item["touch_percent"],
                item["fine_weight"],
                item["rate"],
                item["mc_amount"],
                item["receipt_issue"],
                item["pieces_raw"],
                item["gross_raw"],
                item["less_raw"],
                item["net_raw"],
                item["touch_raw"],
                item["pure_raw"],
                item["rate_raw"],
                item["mc_raw"],
                item["weight_unit"],
                item["rate_unit"]
            ))

        con.execute("""
            INSERT INTO audit_log(
                transaction_id,action,description,created_at
            )
            VALUES(?,?,?,?)
        """, (
            tx_id,
            action,
            f"{action}: {bill_number}",
            now.isoformat(timespec="seconds")
        ))

        con.commit()
        return tx_id

    except Exception:

        con.rollback()
        raise

    finally:

        con.close()


# ============================================================
# RECEIPT
# ============================================================

def receipt_html(tx, items):

    rows = ""

    for _, item in items.iterrows():

        gross = item.get("gross_raw", item["gross_weight"])
        less = item.get("less_raw", item["less_weight"])
        net = item.get("net_raw", item["net_weight"])
        touch = item.get("touch_raw", item["touch_percent"])
        pure = item.get("pure_raw", item["fine_weight"])
        rate = item.get("rate_raw", item["rate"])
        mc = item.get("mc_raw", item["mc_amount"])

        rows += f"""
        <tr>
            <td>{html.escape(str(item['item_name']))}</td>
            <td>{html.escape(str(item['pieces_raw']))}</td>
            <td>{html.escape(str(gross))} {html.escape(str(item.get("weight_unit", "KG")))}</td>
            <td>{html.escape(str(less))} {html.escape(str(item.get("weight_unit", "KG")))}</td>
            <td>{html.escape(str(net))} {html.escape(str(item.get("weight_unit", "KG")))}</td>
            <td>{html.escape(str(touch))}</td>
            <td>{html.escape(str(pure))} {html.escape(str(item.get("weight_unit", "KG")))}</td>
            <td>{html.escape(str(rate))} {html.escape(str(item.get("rate_unit", "Per Gm")))}</td>
            <td>{html.escape(str(mc))}</td>
            <td>{html.escape(str(item['receipt_issue']))}</td>
        </tr>
        """

    tax_rows = ""

    if tx["tax_type"] == "Local":

        tax_rows = f"""
        <tr><td>CGST</td><td>{rupees(tx['cgst'])}</td></tr>
        <tr><td>SGST</td><td>{rupees(tx['sgst'])}</td></tr>
        """

    else:

        tax_rows = f"""
        <tr><td>IGST</td><td>{rupees(tx['igst'])}</td></tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
    <meta charset="UTF-8">

    <style>

    body {{
        font-family: Arial;
        color: #111;
        padding: 15px;
    }}

    .paper {{
        max-width: 950px;
        margin: auto;
        padding: 20px;
        border: 1px solid #333;
    }}

    h1 {{
        text-align: center;
        font-size: 23px;
        margin-bottom: 5px;
    }}

    .address {{
        text-align: center;
        line-height: 1.6;
        font-size: 12px;
    }}

    .heading {{
        text-align: center;
        font-size: 19px;
        font-weight: bold;
        margin: 15px;
    }}

    .details {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        line-height: 1.9;
        font-size: 12px;
        margin: 15px 0;
    }}

    table {{
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
    }}

    td, th {{
        border: 1px solid #333;
        padding: 7px 4px;
        text-align: center;
    }}

    th {{
        background: #e9eff7;
    }}

    .total {{
        margin-top: 15px;
        width: 55%;
        margin-left: auto;
    }}

    .signature {{
        display: flex;
        justify-content: space-between;
        margin-top: 90px;
    }}

    .footer {{
        text-align: center;
        border-top: 1px solid #333;
        margin-top: 30px;
        padding-top: 10px;
        font-size: 11px;
    }}

    button {{
        padding: 10px 25px;
        background: #0750a6;
        color: white;
        border: none;
        cursor: pointer;
        margin-bottom: 12px;
    }}

    @media print {{
        button {{display:none}}
        @page {{size:A4 landscape;margin:10mm}}
        body {{padding:0}}
        .paper {{border:none}}
    }}

    </style>
    </head>

    <body>

    <button onclick="window.print()">PRINT</button>

    <div class="paper">

        <h1>{SHOP_NAME}</h1>

        <div class="address">
            {SHOP_ADDRESS}<br>
            Tel: {SHOP_PHONE}<br>
            Centrex: {SHOP_CENTREX}
        </div>

        <div class="heading">ROUGH ESTIMATION</div>

        <div class="details">

            <div>
                <b>Bill Number:</b>
                {html.escape(str(tx['reference_number']))}<br>

                <b>Customer:</b>
                {html.escape(str(tx['customer_name'] or ''))}<br>

                <b>Customer Number:</b>
                {html.escape(str(tx['customer_number'] or ''))}<br>

                <b>Mobile:</b>
                {html.escape(str(tx['phone'] or ''))}<br>

                <b>Address:</b>
                {html.escape(str(tx['customer_address'] or ''))}
            </div>

            <div>
                <b>Date:</b>
                {tx['transaction_date']}<br>

                <b>Time:</b>
                {tx['transaction_time']}<br>

                <b>Transaction:</b>
                {html.escape(str(tx['transaction_type']))}<br>

                <b>GST:</b>
                {tx['gst_percent']}%<br>

                <b>Narration:</b>
                {html.escape(str(tx['narration'] or ''))}
            </div>

        </div>

        <table>

            <thead>
                <tr>
                    <th>Details</th>
                    <th>Pcs</th>
                    <th>G.Wt</th>
                    <th>Less</th>
                    <th>N.Wt</th>
                    <th>%</th>
                    <th>Pure</th>
                    <th>Rate</th>
                    <th>MC</th>
                    <th>Type</th>
                </tr>
            </thead>

            <tbody>
                {rows}
            </tbody>

        </table>

        <table style="margin-top:15px">

            <tr>
                <th>Sales Pure</th>
                <th>Receipt Pure</th>
                <th>Metal Due</th>
                <th>Sales MC</th>
                <th>Receipt MC</th>
                <th>Amount Due</th>
            </tr>

            <tr>
                <td>{tx['sales_pure']}</td>
                <td>{tx['receipt_pure']}</td>
                <td>{tx['metal_due']}</td>
                <td>{rupees(tx['sales_mc'])}</td>
                <td>{rupees(tx['receipt_mc'])}</td>
                <td>{rupees(tx['amount_due'])}</td>
            </tr>

        </table>

        <table class="total">

            <tr>
                <td>Amount Due</td>
                <td>{rupees(tx['subtotal'])}</td>
            </tr>

            {tax_rows}

            <tr>
                <th>Grand Total</th>
                <th>{rupees(tx['grand_total'])}</th>
            </tr>

        </table>

        <div class="signature">
            <div>Customer Signature</div>
            <div>Authorised Signature</div>
        </div>

        <div class="footer">
            {SHOP_NAME}<br>
            {SHOP_ADDRESS}<br>
            {SHOP_PHONE}
        </div>

    </div>

    </body>
    </html>
    """


# ============================================================
# EXCEL
# ============================================================

def create_excel(start_date, end_date):

    con = get_db()

    bills = pd.read_sql_query("""
        SELECT * FROM transactions
        WHERE transaction_date BETWEEN ? AND ?
        ORDER BY id
    """, con, params=(str(start_date), str(end_date)))

    items = pd.read_sql_query("""
        SELECT
            t.reference_number,
            t.transaction_type,
            t.transaction_date,
            t.transaction_time,
            t.customer_name,
            t.customer_number,
            t.phone,
            t.customer_address,
            i.category,
            i.item_name,
            i.pieces_raw,
            i.gross_raw,
            i.less_raw,
            i.net_raw,
            i.touch_raw,
            i.pure_raw,
            i.rate_raw,
            i.mc_raw,
            i.receipt_issue
        FROM transaction_items i
        JOIN transactions t
        ON t.id=i.transaction_id
        WHERE t.transaction_date BETWEEN ? AND ?
        ORDER BY t.id,i.id
    """, con, params=(str(start_date), str(end_date)))

    con.close()

    output = io.BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        bills.to_excel(
            writer,
            sheet_name="Bill Summary",
            index=False
        )

        items.to_excel(
            writer,
            sheet_name="Item Details",
            index=False
        )

    return output.getvalue()


# ============================================================
# SESSION
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"

if "preview" not in st.session_state:
    st.session_state.preview = None

if "found_bill" not in st.session_state:
    st.session_state.found_bill = None


# ============================================================
# 3D BLUE DESIGN - KEEP THE EXISTING LOOK
# ============================================================

st.markdown("""
<style>

.stApp {
    background: linear-gradient(
        135deg,
        #eaf2ff,
        #ffffff,
        #e2edff
    );
    color: #102b50;
}

[data-testid="stSidebar"] {
    background: linear-gradient(
        155deg,
        #062b62,
        #0c4b9b,
        #1674cf
    );
}

[data-testid="stSidebar"] * {
    color: white !important;
}

.brand {
    color: #08458f;
    font-size: 29px;
    font-weight: 900;
    letter-spacing: 1px;
}

.page-title {
    color: #08458f;
    font-size: 30px;
    font-weight: 900;
    margin-bottom: 15px;
}

.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    background: linear-gradient(
        145deg,
        #287fe0,
        #0750a6
    ) !important;

    color: white !important;
    border: 1px solid #4b95ed !important;
    border-radius: 11px !important;
    font-weight: 800 !important;
    min-height: 42px;

    box-shadow:
        5px 5px 12px #9bb8df,
        -4px -4px 10px white !important;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(145deg,#ffffff,#edf4ff);
    border: 1px solid #d6e5fa;
    border-radius: 16px;
    box-shadow:
        7px 7px 18px #c6d6eb,
        -5px -5px 14px white;
    padding: 8px;
}

[data-testid="stMetric"] {
    background: linear-gradient(145deg,#fff,#edf4ff);
    padding: 14px;
    border-radius: 13px;
    box-shadow:
        5px 5px 12px #cbd9ec,
        -4px -4px 10px white;
}

input, textarea, [data-baseweb="select"] > div {
    border-radius: 9px !important;
}

/* 3D SIDEBAR NAVIGATION */
[data-testid="stSidebar"] {
    box-shadow: 8px 0 24px rgba(4, 31, 75, .28);
}
[data-testid="stSidebar"] [role="radiogroup"] { gap: 9px; }
[data-testid="stSidebar"] [role="radio"] {
    background: linear-gradient(145deg, rgba(255,255,255,.16), rgba(0,28,76,.18));
    border: 1px solid rgba(255,255,255,.20);
    border-radius: 12px;
    padding: 9px 12px;
    box-shadow: 3px 4px 8px rgba(0,0,0,.18);
    transition: transform .15s ease, background .15s ease;
}
[data-testid="stSidebar"] [role="radio"]:hover {
    transform: translateX(4px);
    background: linear-gradient(145deg, rgba(255,255,255,.28), rgba(0,35,90,.25));
}
[data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
    background: linear-gradient(145deg, #48a1ff, #0750a6);
    border: 1px solid #a9d2ff;
    box-shadow: 0 0 0 2px rgba(255,255,255,.18), 0 7px 15px rgba(0,0,0,.30);
}
[data-testid="stSidebar"] .stButton > button {
    box-shadow: 0 5px 0 #063b7a, 0 9px 16px rgba(0,0,0,.25) !important;
}
[data-testid="stSidebar"] .stButton > button:active {
    transform: translateY(3px);
    box-shadow: 0 2px 0 #063b7a !important;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# LOGIN
# ============================================================

def login_screen():

    _, center, _ = st.columns([1, 1.25, 1])

    with center:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#ffffff,#e8f2ff);
        padding:28px;border-radius:22px;text-align:center;
        box-shadow:10px 10px 24px #bdcfe5,-8px -8px 22px #ffffff;
        border:1px solid #d7e6fa;margin:35px 0 18px 0;">
          <div style="font-size:48px">💎</div>
          <div style="font-size:27px;font-weight:950;color:#08458f;letter-spacing:1px;">
          SHREE BALAJI SILVER</div>
          <div style="font-size:12px;color:#53749c;font-weight:700;margin-top:5px;">
          BILLING MANAGEMENT</div>
        </div>
        """, unsafe_allow_html=True)

        login_tab, register_tab = st.tabs(["LOGIN", "NEW REGISTER"])

        with login_tab:
            with st.form("login_form"):
                username = st.text_input("Username", key="login_username")
                password = st.text_input("Password", type="password", key="login_password")
                submit = st.form_submit_button("LOGIN", use_container_width=True)

            if submit:
                con = get_db()
                user = con.execute(
                    "SELECT * FROM users WHERE username=? AND password=?",
                    (username.strip(), hashlib.sha256(password.encode()).hexdigest())
                ).fetchone()
                con.close()
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = username.strip()
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

        with register_tab:
            st.info("Create a separate login account. Usernames must be unique.")
            with st.form("register_form"):
                new_username = st.text_input("Choose Username", key="register_username")
                new_password = st.text_input("Create Password", type="password", key="register_password")
                confirm = st.text_input("Confirm Password", type="password", key="register_confirm")
                register = st.form_submit_button("CREATE ACCOUNT", use_container_width=True)

            if register:
                clean_username = new_username.strip()
                if len(clean_username) < 3:
                    st.error("Username must contain at least 3 characters.")
                elif len(new_password) < 6:
                    st.error("Password must contain at least 6 characters.")
                elif new_password != confirm:
                    st.error("Passwords do not match.")
                else:
                    con = get_db()
                    try:
                        con.execute(
                            "INSERT INTO users(username,password) VALUES(?,?)",
                            (clean_username, hashlib.sha256(new_password.encode()).hexdigest())
                        )
                        con.commit()
                        st.success("Account created. Please use the LOGIN tab.")
                    except sqlite3.IntegrityError:
                        st.error("That username is already registered. Choose another.")
                    finally:
                        con.close()


if not st.session_state.logged_in:

    login_screen()
    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.markdown("""
    <div style="text-align:center;padding:15px">
        <div style="font-size:42px">💎</div>
        <div style="font-size:20px;font-weight:900">
            SHREE BALAJI SILVER
        </div>
        <div style="font-size:11px">
            BILLING MANAGEMENT
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    pages = [
        "Dashboard",
        "Create Bill",
        "Receipt History",
        "Excel Reports",
        "Customer Details",
        "Settings"
    ]

    selected_page = st.radio(
        "NAVIGATION",
        pages,
        index=pages.index(st.session_state.page)
        if st.session_state.page in pages else 0
    )

    st.session_state.page = selected_page

    st.markdown("---")

    st.write("User:", st.session_state.username)

    if st.button("LOG OUT", use_container_width=True):

        st.session_state.logged_in = False
        st.rerun()


st.markdown(
    "<div class='brand'>SHREE BALAJI SILVER</div>",
    unsafe_allow_html=True
)


# ============================================================
# DASHBOARD
# ============================================================

if selected_page == "Dashboard":

    st.markdown(
        "<div class='page-title'>Dashboard</div>",
        unsafe_allow_html=True
    )

    # LIVE CLOCK
    components.html("""
    <div style="
        background:linear-gradient(145deg,#ffffff,#e7f1ff);
        padding:18px;
        border-radius:15px;
        box-shadow:5px 5px 12px #c5d5eb,
        -4px -4px 10px white;
        font-family:Arial;
        text-align:center;
        color:#0750a6;
    ">
        <div style="font-size:13px;font-weight:bold">
            CURRENT DATE & TIME
        </div>
        <div id="clock" style="
            font-size:27px;
            font-weight:900;
            margin-top:8px;
        "></div>
    </div>

    <script>
    function updateClock() {
        const now = new Date();

        document.getElementById("clock").innerText =
            now.toLocaleDateString("en-IN", {
                weekday:"long",
                day:"2-digit",
                month:"long",
                year:"numeric"
            }) + " | " +
            now.toLocaleTimeString("en-IN");
    }

    updateClock();
    setInterval(updateClock,1000);
    </script>
    """, height=105)

    st.markdown("### 📅 Professional Calendar")

    # DATE CALENDAR
    selected_day = st.date_input(
        "Select Transaction Date",
        value=date.today(),
        key="dashboard_calendar"
    )

    st.markdown("---")

    con = get_db()

    daily = pd.read_sql_query("""
        SELECT
            reference_number,
            transaction_type,
            customer_name,
            phone,
            transaction_date,
            transaction_time,
            metal_due,
            amount_due,
            grand_total
        FROM transactions
        WHERE transaction_date=?
        ORDER BY id DESC
    """, con, params=(str(selected_day),))

    recent = pd.read_sql_query("""
        SELECT
            reference_number,
            transaction_type,
            customer_name,
            phone,
            transaction_date,
            transaction_time,
            metal_due,
            amount_due,
            grand_total
        FROM transactions
        ORDER BY id DESC
        LIMIT 10
    """, con)

    con.close()

    st.markdown("### Transactions on Selected Date")

    if daily.empty:

        st.info("No transactions available for this date.")

    else:

        st.dataframe(
            daily,
            use_container_width=True,
            hide_index=True
        )

    st.markdown("---")

    st.markdown("### 🕒 Recent Transactions")

    if recent.empty:

        st.info("No recent transactions available.")

    else:

        st.dataframe(
            recent,
            use_container_width=True,
            hide_index=True
        )

        selected_recent = st.selectbox(
            "Open Recent Bill",
            recent["reference_number"].tolist()
        )

        if st.button("VIEW RECENT BILL"):

            st.session_state.found_bill = selected_recent
            st.session_state.page = "Receipt History"
            st.rerun()

    st.markdown("---")

    if st.button("＋ CREATE NEW BILL", use_container_width=True):

        st.session_state.preview = None
        st.session_state.page = "Create Bill"
        st.rerun()


# ============================================================
# CREATE BILL
# ============================================================

elif selected_page == "Create Bill":

    st.markdown(
        "<div class='page-title'>Create Bill / Rough Estimation</div>",
        unsafe_allow_html=True
    )

    mode = st.radio(
        "Bill Mode",
        ["New Bill", "Correction / Edit Existing Bill"],
        horizontal=True
    )

    existing = get_all_transactions()

    current = None

    if mode == "New Bill":

        bill_number = generate_bill_number()

        st.success(
            f"NEW BILL NUMBER: {bill_number}"
        )

        operation = "Addition"

    else:

        if existing.empty:

            st.warning("No saved bills available.")
            st.stop()

        chosen = st.selectbox(
            "Select Existing Bill Number",
            existing["reference_number"].tolist()
        )

        current = get_bill(chosen)
        bill_number = chosen
        operation = "Correction"

        st.info(
            f"Correcting existing bill: {bill_number}"
        )

    # CUSTOMER
    st.markdown("### Customer & Transaction Details")

    customers = get_customers()

    names = (
        customers["name"].tolist()
        if not customers.empty else []
    )

    debtors = sorted(
        set(get_master("Sundry Debtors") + names)
    )

    old_name = current["customer_name"] if current else ""
    old_number = current["customer_number"] if current else ""
    old_phone = current["phone"] if current else ""

    old_address = current["customer_address"] if current else ""

    old_date = (
        date.fromisoformat(current["transaction_date"])
        if current else date.today()
    )

    old_time = (
        datetime.strptime(
            current["transaction_time"], "%H:%M:%S"
        ).time()
        if current else datetime.now().time().replace(microsecond=0)
    )

    old_type = (
        current["transaction_type"]
        if current else "Sales"
    )

    a, b, c = st.columns(3)

    with a:

        st.text_input(
            "Bill Number",
            value=bill_number,
            disabled=True
        )

        transaction_type = st.selectbox(
            "Transaction Type",
            TRANSACTION_TYPES,
            index=TRANSACTION_TYPES.index(old_type)
            if old_type in TRANSACTION_TYPES else 0
        )

    with b:

        transaction_date = st.date_input(
            "Date",
            value=old_date
        )

        transaction_time = st.time_input(
            "Time",
            value=old_time
        )

    with c:

        narration = st.text_input(
            "Narration",
            value=current["narration"] or ""
            if current else ""
        )

    st.markdown("### Sundry Debtors")

    debtor = st.selectbox(
        "Select Customer",
        ["Enter New Customer"] + debtors,
        index=debtors.index(old_name) + 1
        if old_name in debtors else 0
    )

    if debtor in debtors:

        match = (
            customers[customers["name"] == debtor]
            if not customers.empty else pd.DataFrame()
        )

        if not match.empty:

            match = match.iloc[0]

            default_number = str(match["customer_number"] or "")
            default_phone = str(match["phone"] or "")
            default_address = str(match["address"] or "")

        else:

            default_number = old_number
            default_phone = old_phone
            default_address = old_address

    else:

        default_number = old_number
        default_phone = old_phone
        default_address = old_address

    x, y = st.columns(2)

    with x:

        customer_name = st.text_input(
            "Customer Name",
            value=(
                debtor if debtor != "Enter New Customer"
                else old_name
            )
        )

        customer_number = st.text_input(
            "Customer Number",
            value=default_number
        )

    with y:

        phone = st.text_input(
            "Mobile Number",
            value=default_phone
        )

        # Address is retrieved from customer records.
        # No address/location input in Create Bill.
        customer_address = default_address

    # GST
    st.markdown("### GST Details")

    x, y = st.columns(2)

    with x:

        gst_percent = st.text_input(
            "GST %",
            value=str(current["gst_percent"])
            if current else ""
        )

    with y:

        tax_options = ["Local", "Interstate"]

        old_tax = current["tax_type"] if current else "Local"

        tax_type = st.selectbox(
            "Tax Type",
            tax_options,
            index=tax_options.index(old_tax)
            if old_tax in tax_options else 0
        )

    # ITEM MASTER
    categories = get_master("Category")
    item_options = get_master("Item")

    st.markdown("---")
    st.markdown("### Jewellery Calculation Details")

    st.info(
        "All numeric fields are manual-entry fields. "
        "Type your own values. Decimal zeros are preserved. "
        "The system will not automatically fill your numbers."
    )

    if current:

        old_items = get_items(current["id"])

        starter = pd.DataFrame([{
            "Category": row["category"],
            "Item Name": row["item_name"],
            "Pcs": str(row["pieces_raw"]),
            "Gross Wt": str(row["gross_raw"]),
            "Less Wt": str(row["less_raw"]),
            "Net Wt": str(row["net_raw"]),
            "Touch %": str(row["touch_raw"]),
            "Pure / Fine Wt": str(row["pure_raw"]),
            "Rate": str(row["rate_raw"]),
            "Rate Unit": str(row["rate_unit"] or "Per Gm"),
            "Weight Unit": str(row["weight_unit"] or "KG"),
            "MC Amount": str(row["mc_raw"]),
            "Rec / Issue": row["receipt_issue"]
        } for _, row in old_items.iterrows()])

    else:

        starter = pd.DataFrame([{
            "Category": "",
            "Item Name": "",
            "Pcs": "",
            "Gross Wt": "",
            "Less Wt": "",
            "Net Wt": "",
            "Touch %": "",
            "Pure / Fine Wt": "",
            "Rate": "",
            "Rate Unit": "Per Gm",
            "Weight Unit": "KG",
            "MC Amount": "",
            "Rec / Issue": "Sales"
        }])

    # ALL NUMBERS ARE TEXT TO PRESERVE 0.10, 0.100, 1.00
    edited = st.data_editor(
        starter,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        key="manual_entry_" + bill_number,

        column_config={

            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=categories
            ),

            "Item Name": st.column_config.SelectboxColumn(
                "Item Name",
                options=item_options
            ),

            "Pcs": st.column_config.TextColumn(
                "Pcs",
                help="Enter your own number."
            ),

            "Gross Wt": st.column_config.TextColumn(
                "Gross Wt (Selected Unit)",
                help="Example: 0.10"
            ),

            "Less Wt": st.column_config.TextColumn(
                "Less Wt (Selected Unit)",
                help="Example: 0.010"
            ),

            "Net Wt": st.column_config.TextColumn(
                "Net Wt (Selected Unit)",
                help="Enter your own number."
            ),

            "Touch %": st.column_config.TextColumn(
                "Touch (%)",
                help="Example: 90.00"
            ),

            "Pure / Fine Wt": st.column_config.TextColumn(
                "Pure / Fine Wt",
                help="Enter your own number."
            ),

            "Rate": st.column_config.TextColumn(
                "Rate",
                help="Enter your own rate."
            ),

            "Rate Unit": st.column_config.SelectboxColumn(
                "Rate Unit",
                options=["Per Gm", "Per KG"],
                required=True
            ),

            "Weight Unit": st.column_config.SelectboxColumn(
                "Weight Unit",
                options=["Gm", "KG"],
                required=True
            ),

            "MC Amount": st.column_config.TextColumn(
                "MC Amount",
                help="Enter your own MC amount."
            ),

            "Rec / Issue": st.column_config.SelectboxColumn(
                "Receipt / Issue",
                options=["Sales", "Receipt"]
            )
        }
    )

    # ADD NEW MASTER OPTIONS
    with st.expander("＋ ADD NEW OPTIONS"):

        a, b, c = st.columns(3)

        with a:

            st.write("Sundry Debtors")

            new_debtor = st.text_input(
                "New Debtor",
                key="new_debtor"
            )

            if st.button("SAVE DEBTOR"):

                if add_master("Sundry Debtors", new_debtor):
                    st.success("Debtor saved.")
                    st.rerun()
                else:
                    st.error("Enter a new value.")

        with b:

            st.write("Category")

            new_category = st.text_input(
                "New Category",
                key="new_category"
            )

            if st.button("SAVE CATEGORY"):

                if add_master("Category", new_category):
                    st.success("Category saved.")
                    st.rerun()
                else:
                    st.error("Enter a new value.")

        with c:

            st.write("Item")

            new_item = st.text_input(
                "New Item",
                key="new_item"
            )

            if st.button("SAVE ITEM"):

                if add_master("Item", new_item):
                    st.success("Item saved.")
                    st.rerun()
                else:
                    st.error("Enter a new value.")


    # PREPARE CALCULATIONS
    items = []
    calculation_error = None

    try:
        items = prepare_items(edited)

    except Exception as error:
        calculation_error = str(error)
        st.error(calculation_error)

    # CALCULATION SUMMARY
    if items:
        summary = calculate_summary(items)

        st.markdown("---")
        st.markdown("### Calculation Summary")

        a, b, c = st.columns(3)

        a.metric(
            "Sales Pure",
            f'{summary["sales_pure"]:.3f} Gm'
        )

        b.metric(
            "Receipt Pure",
            f'{summary["receipt_pure"]:.3f} Gm'
        )

        c.metric(
            "Metal Due",
            f'{summary["metal_due"]:.3f} Gm'
        )

        a, b, c = st.columns(3)

        a.metric(
            "Silver Amount",
            rupees(summary["sales_value"] - summary["receipt_value"])
        )

        b.metric(
            "MC Amount Due",
            rupees(summary["sales_mc"] - summary["receipt_mc"])
        )

        c.metric(
            "Amount Due",
            rupees(summary["amount_due"])
        )

        try:
            gst_value = number(gst_percent)

            tax = calculate_gst(
                summary["amount_due"],
                gst_value,
                tax_type
            )

            a, b = st.columns(2)

            a.metric(
                "GST Amount",
                rupees(tax["total_tax"])
            )

            b.metric(
                "GRAND TOTAL",
                rupees(tax["grand_total"])
            )

        except Exception:
            st.warning(
                "Enter a valid GST percentage to calculate the total."
            )


    

    # SAVE AND PREVIEW
    st.markdown("---")

    x, y = st.columns(2)

    with x:

        preview_clicked = st.button(
            "PREVIEW ROUGH ESTIMATION",
            use_container_width=True
        )

    with y:

        save_clicked = st.button(
            "SAVE BILL",
            use_container_width=True
        )

    payload = {
        "bill_number": bill_number,
        "operation": operation,
        "transaction_type": transaction_type,
        "customer_name": customer_name,
        "customer_number": customer_number,
        "phone": phone,
        "customer_address": customer_address,
        "transaction_date": transaction_date,
        "transaction_time": transaction_time,
        "narration": narration,
        "gst_percent": gst_percent,
        "tax_type": tax_type
    }

    def make_preview():

        if calculation_error or not items:
            st.error("Please correct the entered values.")
            return

        if not customer_name.strip():
            st.error("Customer name is required.")
            return

        try:

            gst_value = number(gst_percent)

            summary = calculate_summary(items)

            tax = calculate_gst(
                summary["amount_due"],
                gst_value,
                tax_type
            )

            tx = {
                "reference_number": bill_number,
                "transaction_type": transaction_type,
                "customer_name": customer_name,
                "customer_number": customer_number,
                "phone": phone,
                "customer_address": customer_address,
                "transaction_date": str(transaction_date),
                "transaction_time": str(transaction_time),
                "narration": narration,
                "gst_percent": float(gst_value),
                "tax_type": tax_type,
                "sales_pure": float(summary["sales_pure"]),
                "receipt_pure": float(summary["receipt_pure"]),
                "metal_due": float(summary["metal_due"]),
                "sales_mc": float(summary["sales_mc"]),
                "receipt_mc": float(summary["receipt_mc"]),
                "amount_due": float(summary["amount_due"]),
                "subtotal": float(summary["amount_due"]),
                "cgst": float(tax["cgst"]),
                "sgst": float(tax["sgst"]),
                "igst": float(tax["igst"]),
                "grand_total": float(tax["grand_total"])
            }

            item_df = pd.DataFrame(items)

            st.session_state.preview = {
                "tx": tx,
                "items": item_df
            }

        except Exception as error:

            st.error(str(error))

    if preview_clicked:

        make_preview()

    if save_clicked:

        try:

            if calculation_error:
                raise ValueError(calculation_error)

            if not customer_name.strip():
                raise ValueError("Enter customer name.")

            # Validate GST.
            number(gst_percent)

            tx_id = save_bill(payload, items)

            save_customer(
                customer_number,
                customer_name,
                phone,
                customer_address
            )

            con = get_db()

            saved = con.execute("""
                SELECT * FROM transactions WHERE id=?
            """, (tx_id,)).fetchone()

            con.close()

            st.session_state.preview = {
                "tx": dict(saved),
                "items": get_items(tx_id)
            }

            st.success(
                f"Bill saved successfully: {bill_number}"
            )

            st.info(
                "Your bill is saved. Use the same bill number "
                "in Receipt History to retrieve it."
            )

        except Exception as error:

            st.error(str(error))

    # RECEIPT PREVIEW
    if st.session_state.preview:

        st.markdown("---")
        st.markdown("### ROUGH ESTIMATION - PREVIEW")

        components.html(
            receipt_html(
                st.session_state.preview["tx"],
                st.session_state.preview["items"]
            ),
            height=950,
            scrolling=True
        )


# ============================================================
# RECEIPT HISTORY
# ============================================================

elif selected_page == "Receipt History":

    st.markdown(
        "<div class='page-title'>Receipt History</div>",
        unsafe_allow_html=True
    )

    transactions = get_all_transactions()

    if transactions.empty:

        st.info("No saved bills.")

    else:

        a, b, c = st.columns(3)

        with a:

            search = st.text_input(
                "Search Bill / Customer / Mobile"
            )

        with b:

            type_filter = st.selectbox(
                "Transaction Type",
                ["All"] + TRANSACTION_TYPES
            )

        with c:

            operation_filter = st.selectbox(
                "Operation",
                ["All", "Addition", "Correction"]
            )

        a, b = st.columns(2)

        with a:

            start_date = st.date_input(
                "From Date",
                date.today().replace(day=1)
            )

        with b:

            end_date = st.date_input(
                "To Date",
                date.today()
            )

        if start_date > end_date:

            st.error("Invalid date range.")
            st.stop()

        filtered = transactions[
            (
                transactions["transaction_date"]
                >= str(start_date)
            )
            &
            (
                transactions["transaction_date"]
                <= str(end_date)
            )
        ].copy()

        if type_filter != "All":

            filtered = filtered[
                filtered["transaction_type"] == type_filter
            ]

        if operation_filter != "All":

            filtered = filtered[
                filtered["operation"] == operation_filter
            ]

        if search:

            mask = (
                filtered["reference_number"].astype(str).str.contains(
                    search, case=False, na=False
                )
                |
                filtered["customer_name"].astype(str).str.contains(
                    search, case=False, na=False
                )
                |
                filtered["phone"].astype(str).str.contains(
                    search, case=False, na=False
                )
            )

            filtered = filtered[mask]

        st.subheader("All Saved Transactions")

        st.dataframe(
            filtered[[
                "reference_number",
                "transaction_type",
                "operation",
                "customer_name",
                "customer_number",
                "phone",
                "customer_address",
                "transaction_date",
                "transaction_time",
                "metal_due",
                "amount_due",
                "grand_total"
            ]],
            use_container_width=True,
            hide_index=True
        )

        if not filtered.empty:

            options = filtered["reference_number"].tolist()

            default_bill = (
                st.session_state.found_bill
                if st.session_state.found_bill in options
                else options[0]
            )

            selected_bill = st.selectbox(
                "Select Bill Number to View Complete Details",
                options,
                index=options.index(default_bill)
            )

            tx = get_bill(selected_bill)

            if tx:

                items = get_items(tx["id"])

                st.markdown("---")
                st.subheader("Complete Customer Details")

                st.write("**Bill Number:**", tx["reference_number"])
                st.write("**Customer Name:**", tx["customer_name"])
                st.write("**Customer Number:**", tx["customer_number"])
                st.write("**Mobile Number:**", tx["phone"])
                st.write("**Address:**", tx["customer_address"])
                st.write("**Transaction:**", tx["transaction_type"])
                st.write("**Date:**", tx["transaction_date"])
                st.write("**Time:**", tx["transaction_time"])
                st.write("**Narration:**", tx["narration"])

                st.subheader("Complete Item Details")

                st.dataframe(
                    items[[
                        "category",
                        "item_name",
                        "pieces_raw",
                        "gross_raw",
                        "less_raw",
                        "net_raw",
                        "touch_raw",
                        "pure_raw",
                        "rate_raw",
                        "mc_raw",
                        "receipt_issue"
                    ]],
                    use_container_width=True,
                    hide_index=True
                )

                st.subheader("Complete Calculations")

                a, b, c = st.columns(3)

                a.metric(
                    "Sales Pure",
                    str(tx["sales_pure"]) + " Gm"
                )

                b.metric(
                    "Receipt Pure",
                    str(tx["receipt_pure"]) + " Gm"
                )

                c.metric(
                    "Metal Due",
                    str(tx["metal_due"]) + " Gm"
                )

                a, b, c = st.columns(3)

                a.metric("Sales MC", rupees(tx["sales_mc"]))
                b.metric("Receipt MC", rupees(tx["receipt_mc"]))
                c.metric("Amount Due", rupees(tx["amount_due"]))

                st.markdown("---")

                components.html(
                    receipt_html(tx, items),
                    height=950,
                    scrolling=True
                )

                st.download_button(
                    "DOWNLOAD BILL DETAILS CSV",
                    data=items.to_csv(index=False).encode("utf-8"),
                    file_name=f"{selected_bill}_items.csv",
                    mime="text/csv"
                )


# ============================================================
# EXCEL REPORTS
# ============================================================

elif selected_page == "Excel Reports":

    st.markdown(
        "<div class='page-title'>Excel Reports</div>",
        unsafe_allow_html=True
    )

    report_type = st.selectbox(
        "Report Type",
        ["Daily", "Monthly", "Custom Range"]
    )

    if report_type == "Daily":

        start_date = st.date_input(
            "Select Date",
            date.today()
        )

        end_date = start_date

    elif report_type == "Monthly":

        month = st.date_input(
            "Select Month",
            date.today()
        )

        start_date = month.replace(day=1)

        end_date = month.replace(
            day=calendar.monthrange(
                month.year,
                month.month
            )[1]
        )

    else:

        a, b = st.columns(2)

        with a:

            start_date = st.date_input(
                "Start Date",
                date.today().replace(day=1)
            )

        with b:

            end_date = st.date_input(
                "End Date",
                date.today()
            )

    if start_date > end_date:

        st.error("Invalid date range.")
        st.stop()

    con = get_db()

    report = pd.read_sql_query("""
        SELECT * FROM transactions
        WHERE transaction_date BETWEEN ? AND ?
        ORDER BY id DESC
    """, con, params=(str(start_date), str(end_date)))

    con.close()

    st.metric("Total Bills", len(report))

    if not report.empty:

        st.metric(
            "Total Amount Due",
            rupees(report["amount_due"].sum())
        )

        st.dataframe(
            report,
            use_container_width=True,
            hide_index=True
        )

        excel = create_excel(start_date, end_date)

        if report_type == "Daily":

            filename = (
                f"SBS_{start_date.strftime('%d-%m-%Y')}_"
                f"{start_date.strftime('%A')}_"
                f"{start_date.year}.xlsx"
            )

        elif report_type == "Monthly":

            filename = (
                f"SBS_{start_date.strftime('%B_%Y')}.xlsx"
            )

        else:

            filename = (
                f"SBS_{start_date}_to_{end_date}.xlsx"
            )

        st.download_button(
            "DOWNLOAD EXCEL REPORT",
            data=excel,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

        # Save a copy in the local exports folder.
        local_name = os.path.join(EXPORT_DIR, filename)

        with open(local_name, "wb") as file:
            file.write(excel)

    else:

        st.info("No transactions for this date range.")


# ============================================================
# CUSTOMER DETAILS
# ============================================================

elif selected_page == "Customer Details":

    st.markdown(
        "<div class='page-title'>Customer Details</div>",
        unsafe_allow_html=True
    )

    with st.form("customer_form"):

        a, b = st.columns(2)

        with a:

            customer_number = st.text_input(
                "Customer Number"
            )

            customer_name = st.text_input(
                "Customer Name"
            )

        with b:

            phone = st.text_input(
                "Mobile Number"
            )

            address = st.text_area(
                "Customer Address"
            )

        submit = st.form_submit_button(
            "SAVE CUSTOMER"
        )

    if submit:

        if not customer_number.strip() or not customer_name.strip():

            st.error(
                "Customer Number and Name are required."
            )

        else:

            save_customer(
                customer_number,
                customer_name,
                phone,
                address
            )

            st.success("Customer saved.")
            st.rerun()

    st.markdown("---")

    customers = get_customers()

    st.subheader("Customer Directory")

    st.dataframe(
        customers,
        use_container_width=True,
        hide_index=True
    )

    if not customers.empty:

        selected_customer = st.selectbox(
            "Select Customer History",
            customers["customer_number"].tolist()
        )

        con = get_db()

        history = pd.read_sql_query("""
            SELECT
                reference_number,
                transaction_type,
                transaction_date,
                transaction_time,
                customer_name,
                phone,
                customer_address,
                metal_due,
                amount_due,
                grand_total
            FROM transactions
            WHERE customer_number=?
            ORDER BY id DESC
        """, con, params=(selected_customer,))

        con.close()

        st.subheader("Complete Customer Transaction History")

        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True
        )


# ============================================================
# SETTINGS
# ============================================================

elif selected_page == "Settings":

    st.markdown(
        "<div class='page-title'>Settings</div>",
        unsafe_allow_html=True
    )

    st.subheader("Business Information")

    st.write("**Business Name:**", SHOP_NAME)
    st.write("**Address:**", SHOP_ADDRESS)
    st.write("**Telephone:**", SHOP_PHONE)
    st.write("**Centrex:**", SHOP_CENTREX)

    st.caption(
        "These details are displayed on the printed receipt."
    )

    st.markdown("---")

    st.subheader("Manage Dropdown Options")

    kind = st.selectbox(
        "Select Dropdown",
        ["Sundry Debtors", "Category", "Item"]
    )

    st.write("Saved Options")

    st.dataframe(
        pd.DataFrame({
            "Saved Options": get_master(kind)
        }),
        use_container_width=True,
        hide_index=True
    )

    new_value = st.text_input(
        "Enter New Option"
    )

    if st.button("ADD NEW OPTION"):

        if add_master(kind, new_value):

            st.success("Option saved.")
            st.rerun()

        else:

            st.error("Enter a new option.")

    st.markdown("---")

    st.subheader("Change Login Password")

    with st.form("password_form"):

        old_password = st.text_input(
            "Current Password",
            type="password"
        )

        new_password = st.text_input(
            "New Password",
            type="password"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        change = st.form_submit_button(
            "UPDATE PASSWORD"
        )

    if change:

        con = get_db()

        user = con.execute("""
            SELECT * FROM users
            WHERE username=?
        """, (
            st.session_state.username,
        )).fetchone()

        old_hash = hashlib.sha256(
            old_password.encode()
        ).hexdigest()

        if not user or user["password"] != old_hash:

            st.error("Incorrect current password.")

        elif len(new_password) < 6:

            st.error("Password must have at least 6 characters.")

        elif new_password != confirm_password:

            st.error("Passwords do not match.")

        else:

            new_hash = hashlib.sha256(
                new_password.encode()
            ).hexdigest()

            con.execute("""
                UPDATE users SET password=?
                WHERE username=?
            """, (
                new_hash,
                st.session_state.username
            ))

            con.commit()

            st.success("Password updated successfully.")

        con.close()


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    "SHREE BALAJI SILVER | PROFESSIONAL BILLING SYSTEM"
)
