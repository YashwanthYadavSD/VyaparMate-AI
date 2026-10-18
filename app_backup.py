from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List
from contextlib import contextmanager
from pathlib import Path
import sqlite3, json, datetime, math

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "vyaparmate.db"

app = FastAPI(title="VyaparMate AI", version="1.0.0",
              description="AI-assisted shop management MVP for small Indian retailers.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=False, allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS products(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL, sku TEXT NOT NULL UNIQUE, category TEXT NOT NULL DEFAULT 'General',
          cost_price REAL NOT NULL CHECK(cost_price >= 0),
          selling_price REAL NOT NULL CHECK(selling_price >= 0),
          quantity INTEGER NOT NULL DEFAULT 0 CHECK(quantity >= 0),
          reorder_level INTEGER NOT NULL DEFAULT 5 CHECK(reorder_level >= 0),
          expiry_date TEXT, supplier TEXT,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sales(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          receipt_no TEXT NOT NULL UNIQUE, total REAL NOT NULL, cost_total REAL NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sale_items(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
          product_id INTEGER NOT NULL REFERENCES products(id),
          product_name TEXT NOT NULL, quantity INTEGER NOT NULL,
          unit_price REAL NOT NULL, unit_cost REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expenses(
          id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL,
          amount REAL NOT NULL CHECK(amount >= 0), note TEXT DEFAULT '',
          expense_date TEXT NOT NULL DEFAULT (date('now'))
        );
        """)
        count = c.execute("SELECT COUNT(*) n FROM products").fetchone()["n"]
        if count == 0:
            demo = [
                ("Rice 5kg","RICE-5KG","Staples",260,320,18,5,None,"Local wholesaler"),
                ("Wheat Atta 5kg","ATTA-5KG","Staples",190,240,12,5,None,"Local wholesaler"),
                ("Sunflower Oil 1L","OIL-1L","Cooking",115,145,4,8,None,"City Distributors"),
                ("Sugar 1kg","SUGAR-1KG","Staples",38,48,20,6,None,"Local wholesaler"),
                ("Bath Soap","SOAP-100","Personal Care",28,38,3,10,None,"Daily Needs"),
                ("Biscuits Pack","BIS-01","Snacks",8,10,45,12,None,"Snack Supply"),
                ("Milk 500ml","MILK-500","Dairy",24,28,8,10,None,"Dairy Partner"),
                ("Tea 250g","TEA-250","Beverages",92,120,7,5,None,"City Distributors"),
                ("Toothpaste","PASTE-100","Personal Care",52,68,15,5,None,"Daily Needs"),
                ("Instant Noodles","NOOD-01","Snacks",11,15,30,10,None,"Snack Supply"),
            ]
            c.executemany("""INSERT INTO products(name,sku,category,cost_price,selling_price,quantity,reorder_level,expiry_date,supplier)
                             VALUES(?,?,?,?,?,?,?,?,?)""", demo)

init_db()

class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    sku: str = Field(min_length=1, max_length=60)
    category: str = Field(default="General", max_length=80)
    cost_price: float = Field(ge=0)
    selling_price: float = Field(ge=0)
    quantity: int = Field(ge=0)
    reorder_level: int = Field(default=5, ge=0)
    expiry_date: Optional[str] = None
    supplier: Optional[str] = ""

class SaleLine(BaseModel):
    product_id: int
    quantity: int = Field(gt=0)

class SaleIn(BaseModel):
    items: List[SaleLine] = Field(min_length=1)

class ExpenseIn(BaseModel):
    category: str = Field(min_length=1, max_length=80)
    amount: float = Field(ge=0)
    note: str = ""
    expense_date: Optional[str] = None

def rowdict(row):
    return dict(row) if row else None

@app.get("/", response_class=HTMLResponse)
def home():
    return HTML

@app.get("/health")
def health():
    return {"status": "ok", "app": "VyaparMate AI", "database": "sqlite"}

@app.get("/api/products")
def list_products(search: str = "", category: str = "", low_stock: bool = False):
    with connect() as c:
        sql = "SELECT * FROM products WHERE (name LIKE ? OR sku LIKE ?)"
        args = [f"%{search}%", f"%{search}%"]
        if category:
            sql += " AND category=?"; args.append(category)
        if low_stock:
            sql += " AND quantity <= reorder_level"
        sql += " ORDER BY name COLLATE NOCASE"
        return [rowdict(r) for r in c.execute(sql, args).fetchall()]

@app.post("/api/products")
def create_product(p: ProductIn):
    try:
        with connect() as c:
            cur = c.execute("""INSERT INTO products(name,sku,category,cost_price,selling_price,quantity,reorder_level,expiry_date,supplier)
            VALUES(?,?,?,?,?,?,?,?,?)""",
            (p.name.strip(), p.sku.strip().upper(), p.category.strip() or "General", p.cost_price,
             p.selling_price, p.quantity, p.reorder_level, p.expiry_date, p.supplier))
            return rowdict(c.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone())
    except sqlite3.IntegrityError as e:
        raise HTTPException(409, "SKU already exists or product values are invalid.") from e

@app.put("/api/products/{product_id}")
def update_product(product_id: int, p: ProductIn):
    try:
        with connect() as c:
            cur = c.execute("""UPDATE products SET name=?,sku=?,category=?,cost_price=?,selling_price=?,quantity=?,
            reorder_level=?,expiry_date=?,supplier=? WHERE id=?""",
            (p.name.strip(),p.sku.strip().upper(),p.category.strip() or "General",p.cost_price,p.selling_price,
             p.quantity,p.reorder_level,p.expiry_date,p.supplier,product_id))
            if cur.rowcount == 0: raise HTTPException(404, "Product not found.")
            return rowdict(c.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone())
    except sqlite3.IntegrityError as e:
        raise HTTPException(409, "SKU already exists or product values are invalid.") from e

@app.delete("/api/products/{product_id}")
def delete_product(product_id: int):
    with connect() as c:
        used = c.execute("SELECT COUNT(*) n FROM sale_items WHERE product_id=?", (product_id,)).fetchone()["n"]
        if used: raise HTTPException(409, "This product has sales history and cannot be deleted. Set quantity to zero instead.")
        cur = c.execute("DELETE FROM products WHERE id=?", (product_id,))
        if cur.rowcount == 0: raise HTTPException(404, "Product not found.")
        return {"deleted": True}

@app.post("/api/sales")
def create_sale(sale: SaleIn):
    with connect() as c:
        try:
            c.execute("BEGIN IMMEDIATE")
            total = 0.0; cost_total = 0.0; prepared = []
            for item in sale.items:
                p = c.execute("SELECT * FROM products WHERE id=?", (item.product_id,)).fetchone()
                if not p: raise HTTPException(404, f"Product {item.product_id} not found.")
                if p["quantity"] < item.quantity:
                    raise HTTPException(400, f"Insufficient stock for {p['name']}. Available: {p['quantity']}.")
                total += p["selling_price"] * item.quantity
                cost_total += p["cost_price"] * item.quantity
                prepared.append((p, item.quantity))
            receipt = "VM-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
            cur = c.execute("INSERT INTO sales(receipt_no,total,cost_total) VALUES(?,?,?)",
                             (receipt, round(total,2), round(cost_total,2)))
            sale_id = cur.lastrowid
            for p, qty in prepared:
                c.execute("UPDATE products SET quantity=quantity-? WHERE id=?", (qty,p["id"]))
                c.execute("""INSERT INTO sale_items(sale_id,product_id,product_name,quantity,unit_price,unit_cost)
                             VALUES(?,?,?,?,?,?)""",
                          (sale_id,p["id"],p["name"],qty,p["selling_price"],p["cost_price"]))
            c.commit()
            return {"id": sale_id, "receipt_no": receipt, "total": round(total,2),
                    "gross_profit": round(total-cost_total,2), "created_at": datetime.datetime.now().isoformat(timespec="seconds")}
        except Exception:
            c.rollback()
            raise

@app.get("/api/sales")
def list_sales(limit: int = 50):
    limit = max(1, min(limit, 200))
    with connect() as c:
        sales = c.execute("SELECT * FROM sales ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        result = []
        for s in sales:
            d = rowdict(s)
            d["items"] = [rowdict(x) for x in c.execute("SELECT product_name,quantity,unit_price,unit_cost FROM sale_items WHERE sale_id=?", (s["id"],)).fetchall()]
            d["gross_profit"] = round(d["total"]-d["cost_total"],2)
            result.append(d)
        return result

@app.get("/api/dashboard")
def dashboard():
    with connect() as c:
        today = datetime.date.today().isoformat()
        sums = c.execute("""SELECT COALESCE(SUM(total),0) sales, COALESCE(SUM(total-cost_total),0) gross_profit,
                            COUNT(*) orders FROM sales WHERE date(created_at)=?""", (today,)).fetchone()
        stock = c.execute("SELECT COALESCE(SUM(quantity*cost_price),0) inventory_value, COUNT(*) products FROM products").fetchone()
        low = c.execute("SELECT COUNT(*) n FROM products WHERE quantity <= reorder_level").fetchone()["n"]
        recent = [rowdict(x) for x in c.execute("SELECT id,receipt_no,total,created_at FROM sales ORDER BY id DESC LIMIT 5").fetchall()]
        top = [rowdict(x) for x in c.execute("""SELECT product_name name, SUM(quantity) quantity FROM sale_items
                 GROUP BY product_id,product_name ORDER BY quantity DESC LIMIT 5""").fetchall()]
        daily = [rowdict(x) for x in c.execute("""SELECT date(created_at) day, SUM(total) sales FROM sales
                 WHERE created_at >= date('now','-6 days') GROUP BY date(created_at) ORDER BY day""").fetchall()]
        return {"today_sales": round(sums["sales"],2), "today_gross_profit": round(sums["gross_profit"],2),
                "today_orders": sums["orders"], "inventory_value": round(stock["inventory_value"],2),
                "product_count": stock["products"], "low_stock_count": low, "recent_sales": recent,
                "top_products": top, "daily_sales": daily}


@app.get("/api/reports")
def reports(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    today = datetime.date.today()
    start = start_date or (today - datetime.timedelta(days=29)).isoformat()
    end = end_date or today.isoformat()

    # Validate dates before using them in SQL queries.
    try:
        start = datetime.date.fromisoformat(start).isoformat()
        end = datetime.date.fromisoformat(end).isoformat()
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Dates must use YYYY-MM-DD format."
        )

    if start > end:
        raise HTTPException(
            status_code=400,
            detail="Start date must be on or before end date."
        )

    with connect() as c:
        sales = c.execute("""
            SELECT
                COUNT(*) AS orders,
                COALESCE(SUM(total), 0) AS sales,
                COALESCE(SUM(cost_total), 0) AS cost,
                COALESCE(SUM(total - cost_total), 0) AS gross_profit
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
        """, (start, end)).fetchone()

        expense_summary = c.execute("""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
        """, (start, end)).fetchone()

        daily_sales = c.execute("""
            SELECT
                date(created_at) AS day,
                COUNT(*) AS orders,
                COALESCE(SUM(total), 0) AS sales,
                COALESCE(SUM(cost_total), 0) AS cost,
                COALESCE(SUM(total - cost_total), 0) AS gross_profit
            FROM sales
            WHERE date(created_at) BETWEEN ? AND ?
            GROUP BY date(created_at)
            ORDER BY day DESC
        """, (start, end)).fetchall()

        daily_expenses = c.execute("""
            SELECT
                expense_date AS day,
                category,
                COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY expense_date, category
            ORDER BY day DESC, category
        """, (start, end)).fetchall()

        expense_categories = c.execute("""
            SELECT
                category,
                COALESCE(SUM(amount), 0) AS total
            FROM expenses
            WHERE expense_date BETWEEN ? AND ?
            GROUP BY category
            ORDER BY total DESC
        """, (start, end)).fetchall()

        total_sales = float(sales["sales"])
        total_cost = float(sales["cost"])
        gross_profit = float(sales["gross_profit"])
        total_expenses = float(expense_summary["total"])

        return {
            "start_date": start,
            "end_date": end,
            "orders": sales["orders"],
            "sales": round(total_sales, 2),
            "cost_of_goods": round(total_cost, 2),
            "gross_profit": round(gross_profit, 2),
            "total_expenses": round(total_expenses, 2),
            "estimated_net_profit": round(
                gross_profit - total_expenses, 2
            ),
            "daily": [rowdict(r) for r in daily_sales],
            "daily_expenses": [
                rowdict(r) for r in daily_expenses
            ],
            "expense_categories": [
                rowdict(r) for r in expense_categories
            ]
        }



@app.get("/api/expenses")
def list_expenses():
    with connect() as c:
        return [rowdict(x) for x in c.execute("SELECT * FROM expenses ORDER BY expense_date DESC,id DESC LIMIT 200").fetchall()]

@app.post("/api/expenses")
def create_expense(e: ExpenseIn):
    with connect() as c:
        cur = c.execute("INSERT INTO expenses(category,amount,note,expense_date) VALUES(?,?,?,?)",
                        (e.category.strip(), e.amount, e.note, e.expense_date or datetime.date.today().isoformat()))
        return rowdict(c.execute("SELECT * FROM expenses WHERE id=?", (cur.lastrowid,)).fetchone())

@app.get("/api/assistant")
def assistant(question: str):
    q = question.lower()
    with connect() as c:
        products = c.execute("SELECT * FROM products").fetchall()
        low = [p for p in products if p["quantity"] <= p["reorder_level"]]
        if any(w in q for w in ["low stock","running out","restock","reorder","stock alert"]):
            if not low: answer = "Great news: no products are currently at or below their reorder thresholds."
            else:
                answer = "Products needing attention: " + "; ".join(
                    f'{p["name"]} (stock {p["quantity"]}, threshold {p["reorder_level"]}; suggested order {max(p["reorder_level"]*2-p["quantity"], p["reorder_level"])} units)'
                    for p in low)
        elif "inventory" in q or "stock value" in q:
            value = sum(p["quantity"]*p["cost_price"] for p in products)
            answer = f"There are {len(products)} products in the catalogue. Estimated inventory value at cost is ₹{value:,.2f}."
        elif "profit" in q or "margin" in q:
            top = c.execute("""SELECT product_name, SUM(quantity*(unit_price-unit_cost)) profit
                               FROM sale_items GROUP BY product_id,product_name ORDER BY profit DESC LIMIT 3""").fetchall()
            answer = "Gross profit leaders from recorded sales: " + ("; ".join(f'{r["product_name"]}: ₹{r["profit"]:,.2f}' for r in top) if top else "no sales recorded yet.")
        elif "today" in q or "sales" in q or "revenue" in q:
            today = datetime.date.today().isoformat()
            s = c.execute("SELECT COALESCE(SUM(total),0) total, COUNT(*) n FROM sales WHERE date(created_at)=?", (today,)).fetchone()
            answer = f"Recorded sales today: ₹{s['total']:,.2f} across {s['n']} orders. This uses saved sales records."
        elif "best" in q or "selling" in q or "popular" in q:
            rows = c.execute("""SELECT product_name, SUM(quantity) qty FROM sale_items GROUP BY product_id,product_name ORDER BY qty DESC LIMIT 5""").fetchall()
            answer = "Best sellers based on recorded quantities: " + ("; ".join(f'{r["product_name"]} ({r["qty"]} units)' for r in rows) if rows else "no sales history yet.")
        else:
            answer = "I can help with sales today, low stock/restocking, inventory value, gross profit, and best-selling products. Ask one of those questions. This is the built-in offline assistant; no external AI provider is connected."
        return {"answer": answer, "mode": "offline-rule-based", "notice": "Uses saved database records; not a cloud AI model."}

@app.get("/api/export/sales.csv")
def export_sales():
    from fastapi.responses import PlainTextResponse
    with connect() as c:
        rows = c.execute("SELECT receipt_no,created_at,total,cost_total,(total-cost_total) gross_profit FROM sales ORDER BY id DESC").fetchall()
    import csv, io
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Receipt","Date","Sales INR","Cost INR","Gross profit INR"])
    for r in rows: writer.writerow(list(r))
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=vyaparmate-sales.csv"})

@app.post("/api/demo/reset")
def reset_demo():
    with connect() as c:
        c.execute("DELETE FROM sale_items"); c.execute("DELETE FROM sales"); c.execute("DELETE FROM expenses"); c.execute("DELETE FROM products")
        demo = [
            ("Rice 5kg","RICE-5KG","Staples",260,320,18,5,None,"Local wholesaler"),
            ("Wheat Atta 5kg","ATTA-5KG","Staples",190,240,12,5,None,"Local wholesaler"),
            ("Sunflower Oil 1L","OIL-1L","Cooking",115,145,4,8,None,"City Distributors"),
            ("Sugar 1kg","SUGAR-1KG","Staples",38,48,20,6,None,"Local wholesaler"),
            ("Bath Soap","SOAP-100","Personal Care",28,38,3,10,None,"Daily Needs"),
            ("Biscuits Pack","BIS-01","Snacks",8,10,45,12,None,"Snack Supply"),
            ("Milk 500ml","MILK-500","Dairy",24,28,8,10,None,"Dairy Partner"),
            ("Tea 250g","TEA-250","Beverages",92,120,7,5,None,"City Distributors"),
            ("Toothpaste","PASTE-100","Personal Care",52,68,15,5,None,"Daily Needs"),
            ("Instant Noodles","NOOD-01","Snacks",11,15,30,10,None,"Snack Supply"),
        ]
        c.executemany("""INSERT INTO products(name,sku,category,cost_price,selling_price,quantity,reorder_level,expiry_date,supplier)
                         VALUES(?,?,?,?,?,?,?,?,?)""", demo)
    return {"status":"reset","message":"Demo data restored."}

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VyaparMate AI — Shop Dashboard</title>
<style>
:root{--bg:#f4f7fb;--panel:#fff;--ink:#172033;--muted:#64748b;--line:#e5eaf2;--accent:#2563eb;--green:#0f9f6e;--orange:#d97706;--red:#dc2626}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 Inter,Segoe UI,Arial,sans-serif}
header{height:72px;background:#fff;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 28px;position:sticky;top:0;z-index:2}
.brand{display:flex;align-items:center;gap:12px;font-size:19px;font-weight:800}.logo{width:38px;height:38px;border-radius:12px;background:linear-gradient(135deg,#2563eb,#10b981);color:white;display:grid;place-items:center;font-weight:900}
.brand small{display:block;color:var(--muted);font-size:11px;font-weight:500}.pill{border-radius:999px;padding:6px 10px;background:#eafaf2;color:#087c54;font-size:12px;font-weight:700}
.layout{display:grid;grid-template-columns:220px 1fr;min-height:calc(100vh - 72px)}aside{background:#fff;border-right:1px solid var(--line);padding:22px 14px}aside button{width:100%;text-align:left;background:transparent;color:#536176;margin:3px 0;padding:12px 14px;border-radius:10px}aside button.active,aside button:hover{background:#edf3ff;color:#1d4ed8}.navlabel{padding:14px 14px 5px;color:#94a3b8;text-transform:uppercase;font-size:10px;font-weight:800;letter-spacing:1px}
main{padding:28px;max-width:1500px;width:100%;margin:auto}.pagehead{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:22px}.pagehead h1{font-size:26px;margin:0 0 3px}.muted{color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:20px}.card{background:var(--panel);border:1px solid var(--line);border-radius:16px;padding:20px;box-shadow:0 2px 7px #15284b05}.metriclabel{color:var(--muted);font-size:12px;font-weight:650}.metric{font-size:26px;font-weight:800;letter-spacing:-.6px;margin:8px 0 3px}.metricfoot{font-size:12px;color:var(--muted)}.two{display:grid;grid-template-columns:1.3fr 1fr;gap:18px;margin-bottom:18px}.card h2{font-size:16px;margin:0 0 15px}.toolbar{display:flex;gap:9px;flex-wrap:wrap;margin-bottom:15px}input,select,textarea{padding:10px 12px;border:1px solid #d9e1ec;border-radius:9px;background:#fff;color:var(--ink);font:inherit;max-width:100%}input:focus,select:focus{outline:2px solid #bfdbfe;border-color:#60a5fa}button{border:0;border-radius:9px;padding:10px 14px;background:var(--accent);color:#fff;font:inherit;font-weight:700;cursor:pointer}button.secondary{background:#edf2f8;color:#334155}button.danger{background:#fee2e2;color:#b91c1c}button.small{padding:6px 9px;font-size:12px}table{width:100%;border-collapse:collapse;min-width:640px}th,td{padding:12px 10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}th{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#8490a3;background:#fafbfd}td{font-size:13px}.tablewrap{overflow:auto}.tag{display:inline-block;border-radius:7px;padding:4px 8px;font-size:11px;font-weight:750;background:#dcfce7;color:#166534}.tag.warn{background:#fef3c7;color:#92400e}.tag.bad{background:#fee2e2;color:#991b1b}.hidden{display:none!important}.barrow{display:grid;grid-template-columns:105px 1fr 65px;gap:10px;align-items:center;margin:13px 0}.barbg{height:10px;background:#edf2f7;border-radius:10px;overflow:hidden}.bar{height:100%;background:linear-gradient(90deg,#2563eb,#34d399);border-radius:10px}.barval{text-align:right;font-weight:700;font-size:12px}.empty{padding:28px;text-align:center;color:var(--muted)}.formgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.field label{display:block;font-size:12px;font-weight:700;margin-bottom:5px}.field input,.field select{width:100%}.modal{position:fixed;inset:0;background:#0f172a88;display:grid;place-items:center;padding:16px;z-index:5}.modalbox{background:#fff;border-radius:18px;padding:24px;width:min(760px,100%);max-height:90vh;overflow:auto}.modalhead{display:flex;justify-content:space-between;align-items:center;margin-bottom:18px}.modalhead h2{margin:0}.assistantbox{display:flex;gap:10px;margin-top:12px}.assistantbox input{flex:1}.answer{padding:16px;border-radius:12px;background:#f0f7ff;margin-top:15px;white-space:pre-wrap}.footnote{font-size:11px;color:var(--muted);margin-top:15px}.toast{position:fixed;bottom:20px;right:20px;padding:13px 18px;background:#172033;color:white;border-radius:10px;box-shadow:0 8px 30px #0002;z-index:8;max-width:90vw}.chartbars{height:190px;display:flex;gap:12px;align-items:end;border-bottom:1px solid var(--line);padding:15px 4px 0}.chartcol{flex:1;min-width:0;text-align:center;height:100%;display:flex;flex-direction:column;justify-content:end;align-items:center;gap:6px}.chartstick{width:min(38px,75%);min-height:3px;border-radius:6px 6px 0 0;background:linear-gradient(180deg,#34d399,#2563eb)}.chartcol small{font-size:10px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;max-width:100%}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}.layout{grid-template-columns:175px 1fr}main{padding:20px}}
@media(max-width:650px){header{padding:0 14px}.layout{display:block}aside{display:flex;overflow:auto;padding:8px;border-right:0;border-bottom:1px solid var(--line);position:sticky;top:72px;z-index:2}aside button{white-space:nowrap;width:auto;margin:0 3px;padding:9px 11px}.navlabel{display:none}main{padding:16px}.grid{gap:10px}.card{padding:15px}.metric{font-size:21px}.pagehead{align-items:flex-start;flex-direction:column}.formgrid{grid-template-columns:1fr 1fr}.brand{font-size:16px}}
</style></head><body>
<header><div class="brand"><div class="logo">V</div><div>VyaparMate AI<small>SMARTER BUSINESS, EVERY DAY</small></div></div><div style="display:flex;gap:10px;align-items:center"><span class="pill">● Local demo mode</span><button class="secondary small" onclick="toggleTheme()">◐ Theme</button></div></header>
<div class="layout"><aside>
<div class="navlabel">Workspace</div>
<button class="active" data-page="dashboard" onclick="navigate('dashboard',this)">▦ &nbsp; Dashboard</button>
<button data-page="inventory" onclick="navigate('inventory',this)">▤ &nbsp; Inventory</button>
<button data-page="sales" onclick="navigate('sales',this)">₹ &nbsp; New Sale</button>
<button data-page="history" onclick="navigate('history',this)">◷ &nbsp; Sales History</button>
<div class="navlabel">Intelligence</div>
<button data-page="assistant" onclick="navigate('assistant',this)">✦ &nbsp; AI Assistant</button>
<button data-page="reports" onclick="navigate('reports',this)">▥ &nbsp; Reports</button>
<button data-page="expenses" onclick="navigate('expenses',this)">↗ &nbsp; Expenses</button>
<div class="navlabel">Manage</div>
<button onclick="resetDemo()">↻ &nbsp; Reset demo data</button>
<div class="footnote" style="padding:12px">MVP • Data stored locally in SQLite on this computer.</div>
</aside><main>
<section id="page-dashboard">
<div class="pagehead"><div><h1>Good business starts here 👋</h1><div class="muted">Here's your shop's performance at a glance.</div></div><button onclick="openProduct()">＋ Add product</button></div>
<div class="grid">
<div class="card"><div class="metriclabel">TODAY'S SALES</div><div class="metric" id="m-sales">₹0</div><div class="metricfoot">Recorded sales today</div></div>
<div class="card"><div class="metriclabel">GROSS PROFIT TODAY</div><div class="metric" id="m-profit">₹0</div><div class="metricfoot">Sales less product cost</div></div>
<div class="card"><div class="metriclabel">INVENTORY VALUE</div><div class="metric" id="m-stock">₹0</div><div class="metricfoot">Estimated at purchase cost</div></div>
<div class="card"><div class="metriclabel">LOW-STOCK ALERTS</div><div class="metric" id="m-low">0</div><div class="metricfoot" id="m-products">0 products in catalogue</div></div>
</div>
<div class="two"><div class="card"><h2>Sales activity · last 7 days</h2><div id="sales-chart" class="chartbars"></div><div class="footnote">Sales shown only for days with recorded transactions.</div></div>
<div class="card"><h2>Products to watch</h2><div id="low-list"></div></div></div>
<div class="two"><div class="card"><h2>Best sellers</h2><div id="top-list"></div></div><div class="card"><h2>Recent transactions</h2><div id="recent-list"></div></div></div>
</section>
<section id="page-inventory" class="hidden"><div class="pagehead"><div><h1>Inventory</h1><div class="muted">Keep every product and stock level in control.</div></div><button onclick="openProduct()">＋ Add product</button></div>
<div class="card"><div class="toolbar"><input id="product-search" placeholder="Search name or SKU..." oninput="loadProducts()" style="flex:1;min-width:170px"><select id="category-filter" onchange="loadProducts()"><option value="">All categories</option></select><button class="secondary" onclick="document.getElementById('low-filter').checked=!document.getElementById('low-filter').checked;loadProducts()">Toggle low stock</button><input type="checkbox" id="low-filter" onchange="loadProducts()" title="Low stock only" style="width:18px"></div><div class="tablewrap"><table><thead><tr><th>Product</th><th>SKU</th><th>Category</th><th>Cost</th><th>Price</th><th>Stock</th><th>Margin</th><th>Actions</th></tr></thead><tbody id="products-body"></tbody></table></div><div class="footnote">Gross margin percentage is calculated from selling price and cost; it is not net profit.</div></div></section>
<section id="page-sales" class="hidden"><div class="pagehead"><div><h1>New sale</h1><div class="muted">Create a sale and update stock atomically.</div></div></div><div class="two"><div class="card"><h2>Choose products</h2><div class="toolbar"><input id="sale-search" placeholder="Search product..." oninput="renderSaleProducts()" style="width:100%"></div><div id="sale-products"></div></div><div class="card"><h2>Current bill</h2><div id="cart-lines" class="empty">Add products to start a bill.</div><div style="display:flex;justify-content:space-between;font-size:18px;font-weight:800;padding:15px 0;border-top:1px solid var(--line)">Total <span id="cart-total">₹0.00</span></div><button style="width:100%" onclick="checkout()">Complete sale</button><div class="footnote">Stock is checked by the server before a sale is saved.</div></div></div></section>
<section id="page-history" class="hidden"><div class="pagehead"><div><h1>Sales history</h1><div class="muted">Review receipts and recorded transactions.</div></div><a href="/api/export/sales.csv" target="_blank"><button class="secondary">↓ Export CSV</button></a></div><div class="card"><div class="tablewrap"><table><thead><tr><th>Receipt</th><th>Date</th><th>Items</th><th>Sales</th><th>Gross profit</th><th></th></tr></thead><tbody id="history-body"></tbody></table></div></div></section>
<section id="page-assistant" class="hidden"><div class="pagehead"><div><h1>Business assistant ✦</h1><div class="muted">Ask questions about your saved shop data.</div></div></div><div class="card"><h2>What would you like to know?</h2><div class="toolbar"><button class="secondary small" onclick="askPreset('Which products need restocking?')">Restock advice</button><button class="secondary small" onclick="askPreset('What were my sales today?')">Today's sales</button><button class="secondary small" onclick="askPreset('What is my inventory value?')">Inventory value</button><button class="secondary small" onclick="askPreset('Which products have highest profit?')">Profit leaders</button></div><div class="assistantbox"><input id="question" placeholder="Ask about sales, stock, profit..." onkeydown="if(event.key==='Enter')ask()"><button onclick="ask()">Ask</button></div><div id="answer" class="answer hidden"></div><div class="footnote">Offline rule-based assistant using your local database. No external AI model is connected in this version.</div></div></section>
<section id="page-reports" class="hidden"><div class="pagehead"><div><h1>Reports & insights</h1><div class="muted">Track performance from actual recorded transactions.</div></div><a href="/api/export/sales.csv" target="_blank"><button class="secondary">↓ Export sales CSV</button></a></div><div class="card"><h2>Daily sales summary</h2><div class="tablewrap"><table><thead><tr><th>Date</th><th>Orders</th><th>Sales</th><th>Gross profit</th></tr></thead><tbody id="reports-body"></tbody></table></div><div class="footnote">Gross profit = sales minus the recorded cost of sold products. It excludes expenses and other operating costs.</div></div></section>
<section id="page-expenses" class="hidden"><div class="pagehead"><div><h1>Business expenses</h1><div class="muted">Record costs such as rent, electricity, or delivery.</div></div><button onclick="openExpense()">＋ Add expense</button></div><div class="card"><div class="tablewrap"><table><thead><tr><th>Date</th><th>Category</th><th>Note</th><th>Amount</th></tr></thead><tbody id="expenses-body"></tbody></table></div></div></section>
</main></div>
<div id="product-modal" class="modal hidden"><div class="modalbox"><div class="modalhead"><h2 id="product-modal-title">Add product</h2><button class="secondary" onclick="closeModal('product-modal')">✕</button></div><form id="product-form" onsubmit="saveProduct(event)"><input type="hidden" id="p-id"><div class="formgrid">
<div class="field"><label>Product name *</label><input id="p-name" required maxlength="120"></div><div class="field"><label>SKU *</label><input id="p-sku" required maxlength="60"></div><div class="field"><label>Category</label><input id="p-category" value="General"></div>
<div class="field"><label>Cost price (₹) *</label><input id="p-cost" type="number" min="0" step=".01" required></div><div class="field"><label>Selling price (₹) *</label><input id="p-price" type="number" min="0" step=".01" required></div><div class="field"><label>Quantity *</label><input id="p-qty" type="number" min="0" step="1" required></div>
<div class="field"><label>Reorder threshold</label><input id="p-reorder" type="number" min="0" value="5"></div><div class="field"><label>Expiry date (optional)</label><input id="p-expiry" type="date"></div><div class="field"><label>Supplier</label><input id="p-supplier"></div>
</div><div style="display:flex;justify-content:end;gap:10px;margin-top:20px"><button type="button" class="secondary" onclick="closeModal('product-modal')">Cancel</button><button type="submit">Save product</button></div></form></div></div>
<div id="expense-modal" class="modal hidden"><div class="modalbox" style="max-width:500px"><div class="modalhead"><h2>Add expense</h2><button class="secondary" onclick="closeModal('expense-modal')">✕</button></div><form onsubmit="saveExpense(event)"><div class="field"><label>Category</label><input id="e-category" required placeholder="Rent, electricity, delivery..."></div><div class="field" style="margin-top:12px"><label>Amount (₹)</label><input id="e-amount" type="number" min="0" step=".01" required></div><div class="field" style="margin-top:12px"><label>Note</label><input id="e-note"></div><div class="field" style="margin-top:12px"><label>Date</label><input id="e-date" type="date"></div><button style="margin-top:18px">Save expense</button></form></div></div>
<div id="toast" class="toast hidden"></div>
<script>
const INR=n=>'₹'+Number(n||0).toLocaleString('en-IN',{minimumFractionDigits:2,maximumFractionDigits:2});
let products=[],cart={};
async function api(url,opts={}){const r=await fetch(url,{headers:{'Content-Type':'application/json'},...opts});let d;try{d=await r.json()}catch{d=await r.text()}if(!r.ok)throw new Error(d.detail||d.message||'Request failed');return d}
function toast(s){const t=document.getElementById('toast');t.textContent=s;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),3200)}
function navigate(page,btn){document.querySelectorAll('main section').forEach(s=>s.classList.add('hidden'));document.getElementById('page-'+page).classList.remove('hidden');document.querySelectorAll('aside button[data-page]').forEach(b=>b.classList.toggle('active',b===btn));({dashboard:loadDashboard,inventory:loadProducts,sales:loadSaleProducts,history:loadHistory,assistant:()=>{},reports:loadReports,expenses:loadExpenses}[page]||(()=>{}))()}
function money(n){return INR(n)}
async function loadDashboard(){try{const d=await api('/api/dashboard');document.getElementById('m-sales').textContent=money(d.today_sales);document.getElementById('m-profit').textContent=money(d.today_gross_profit);document.getElementById('m-stock').textContent=money(d.inventory_value);document.getElementById('m-low').textContent=d.low_stock_count;document.getElementById('m-products').textContent=d.product_count+' products in catalogue';
const days=[];for(let i=6;i>=0;i--){const dt=new Date();dt.setDate(dt.getDate()-i);const key=dt.toISOString().slice(0,10);days.push({day:key,sales:(d.daily_sales.find(x=>x.day===key)||{}).sales||0})}const max=Math.max(1,...days.map(x=>x.sales));document.getElementById('sales-chart').innerHTML=days.map(x=>`<div class="chartcol"><b style="font-size:10px">${x.sales?money(x.sales):''}</b><div class="chartstick" style="height:${Math.max(3,x.sales/max*65)}%"></div><small>${x.day.slice(5)}</small></div>`).join('');
const low=products.length?products.filter(p=>p.quantity<=p.reorder_level):await api('/api/products?low_stock=true');document.getElementById('low-list').innerHTML=low.length?low.slice(0,6).map(p=>`<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--line)"><div><b>${esc(p.name)}</b><div class="muted" style="font-size:11px">Threshold ${p.reorder_level}</div></div><span class="tag ${p.quantity===0?'bad':'warn'}">${p.quantity} left</span></div>`).join(''):'<div class="empty">All products are above their reorder thresholds.</div>';
document.getElementById('top-list').innerHTML=d.top_products.length?d.top_products.map(p=>`<div class="barrow"><span>${esc(p.name)}</span><div class="barbg"><div class="bar" style="width:${Math.min(100,p.quantity/Math.max(1,d.top_products[0].quantity)*100)}%"></div></div><span class="barval">${p.quantity} sold</span></div>`).join(''):'<div class="empty">Record sales to see best sellers.</div>';
document.getElementById('recent-list').innerHTML=d.recent_sales.length?d.recent_sales.map(s=>`<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line)"><div><b>${esc(s.receipt_no)}</b><div class="muted" style="font-size:11px">${esc(s.created_at)}</div></div><b>${money(s.total)}</b></div>`).join(''):'<div class="empty">No sales recorded yet.</div>';
}catch(e){toast(e.message)}}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function loadProducts(){try{products=await api('/api/products?search='+encodeURIComponent(document.getElementById('product-search')?.value||'')+'&low_stock='+(document.getElementById('low-filter')?.checked||false));const cats=[...new Set(products.map(p=>p.category))].sort();const f=document.getElementById('category-filter');const old=f.value;f.innerHTML='<option value="">All categories</option>'+cats.map(x=>`<option>${esc(x)}</option>`).join('');f.value=cats.includes(old)?old:'';let view=products.filter(p=>!f.value||p.category===f.value);document.getElementById('products-body').innerHTML=view.length?view.map(p=>`<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.sku)}</td><td>${esc(p.category)}</td><td>${money(p.cost_price)}</td><td>${money(p.selling_price)}</td><td><span class="tag ${p.quantity<=p.reorder_level?'warn':''}">${p.quantity}</span></td><td>${p.selling_price?((p.selling_price-p.cost_price)/p.selling_price*100).toFixed(1)+'%':'—'}</td><td><button class="secondary small" onclick="editProduct(${p.id})">Edit</button> <button class="danger small" onclick="deleteProduct(${p.id})">Delete</button></td></tr>`).join(''):'<tr><td colspan="8" class="empty">No products match your search.</td></tr>'; }catch(e){toast(e.message)}}
function openProduct(p=null){document.getElementById('product-form').reset();document.getElementById('p-id').value=p?.id||'';document.getElementById('product-modal-title').textContent=p?'Edit product':'Add product';document.getElementById('p-name').value=p?.name||'';document.getElementById('p-sku').value=p?.sku||'';document.getElementById('p-category').value=p?.category||'General';document.getElementById('p-cost').value=p?.cost_price??'';document.getElementById('p-price').value=p?.selling_price??'';document.getElementById('p-qty').value=p?.quantity??0;document.getElementById('p-reorder').value=p?.reorder_level??5;document.getElementById('p-expiry').value=p?.expiry_date||'';document.getElementById('p-supplier').value=p?.supplier||'';document.getElementById('product-modal').classList.remove('hidden')}
function closeModal(id){document.getElementById(id).classList.add('hidden')}
async function saveProduct(ev){ev.preventDefault();const id=document.getElementById('p-id').value;const payload={name:document.getElementById('p-name').value,sku:document.getElementById('p-sku').value,category:document.getElementById('p-category').value||'General',cost_price:+document.getElementById('p-cost').value,selling_price:+document.getElementById('p-price').value,quantity:+document.getElementById('p-qty').value,reorder_level:+document.getElementById('p-reorder').value,expiry_date:document.getElementById('p-expiry').value||null,supplier:document.getElementById('p-supplier').value};try{await api(id?'/api/products/'+id:'/api/products',{method:id?'PUT':'POST',body:JSON.stringify(payload)});closeModal('product-modal');toast('Product saved');await loadProducts();await loadDashboard()}catch(e){toast(e.message)}}
async function editProduct(id){try{const p=await api('/api/products');openProduct(p.find(x=>x.id===id))}catch(e){toast(e.message)}}
async function deleteProduct(id){if(!confirm('Delete this product? Products with sales history cannot be deleted.'))return;try{await api('/api/products/'+id,{method:'DELETE'});toast('Product deleted');loadProducts();loadDashboard()}catch(e){toast(e.message)}}
async function loadSaleProducts(){products=await api('/api/products');renderSaleProducts();renderCart()}
function renderSaleProducts(){const q=(document.getElementById('sale-search')?.value||'').toLowerCase();const arr=products.filter(p=>p.name.toLowerCase().includes(q)||p.sku.toLowerCase().includes(q));document.getElementById('sale-products').innerHTML=arr.map(p=>`<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 0;border-bottom:1px solid var(--line)"><div><b>${esc(p.name)}</b><div class="muted">${money(p.selling_price)} · ${p.quantity} in stock</div></div><button class="small" ${p.quantity===0?'disabled':''} onclick="addCart(${p.id})">＋ Add</button></div>`).join('')||'<div class="empty">No products found.</div>'}
function addCart(id){const p=products.find(x=>x.id===id);if(!p)return;if((cart[id]||0)>=p.quantity){toast('Cannot add more than available stock');return}cart[id]=(cart[id]||0)+1;renderCart()}
function changeCart(id,delta){const p=products.find(x=>x.id===id);cart[id]=(cart[id]||0)+delta;if(cart[id]<=0)delete cart[id];else if(cart[id]>p.quantity){cart[id]=p.quantity;toast('Stock limit reached')}renderCart()}
function renderCart(){const entries=Object.entries(cart);document.getElementById('cart-lines').className=entries.length?'':'empty';document.getElementById('cart-lines').innerHTML=entries.length?entries.map(([id,q])=>{const p=products.find(x=>x.id===+id);return `<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 0;border-bottom:1px solid var(--line)"><div><b>${esc(p.name)}</b><div class="muted">${money(p.selling_price)} each</div></div><div style="display:flex;align-items:center;gap:6px"><button class="secondary small" onclick="changeCart(${id},-1)">−</button>${q}<button class="secondary small" onclick="changeCart(${id},1)">+</button></div><b>${money(p.selling_price*q)}</b></div>`}).join(''):'Add products to start a bill.';document.getElementById('cart-total').textContent=money(entries.reduce((sum,[id,q])=>sum+products.find(p=>p.id===+id).selling_price*q,0))}
async function checkout(){const items=Object.entries(cart).map(([product_id,quantity])=>({product_id:+product_id,quantity}));if(!items.length){toast('Add at least one product');return}try{const s=await api('/api/sales',{method:'POST',body:JSON.stringify({items})});cart={};toast('Sale complete: '+s.receipt_no);await loadSaleProducts();await loadDashboard();await loadHistory();if(confirm(`Sale complete!\nReceipt: ${s.receipt_no}\nTotal: ${money(s.total)}\nGross profit: ${money(s.gross_profit)}\n\nPrint receipt?`)){printReceipt(s)}}catch(e){toast(e.message);await loadSaleProducts()}}
function printReceipt(s){const w=window.open('','_blank','width=420,height=650');if(!w){toast('Allow pop-ups to print the receipt');return}w.document.write(`<html><head><title>Receipt ${esc(s.receipt_no)}</title><style>body{font:14px Arial;padding:25px}h2{text-align:center}hr{border:0;border-top:1px dashed #888}p{display:flex;justify-content:space-between}</style></head><body><h2>VyaparMate AI</h2><p style="justify-content:center">Shop sales receipt</p><hr><p><span>Receipt</span><b>${esc(s.receipt_no)}</b></p><p><span>Date</span><span>${esc(s.created_at)}</span></p><hr><p><b>Total</b><b>${money(s.total)}</b></p><p><span>Gross profit estimate</span><span>${money(s.gross_profit)}</span></p><hr><p style="justify-content:center">Thank you!</p><script>window.print()<\/script></body></html>`);w.document.close()}
async function loadHistory(){try{const a=await api('/api/sales');document.getElementById('history-body').innerHTML=a.length?a.map(s=>`<tr><td><b>${esc(s.receipt_no)}</b></td><td>${esc(s.created_at)}</td><td>${s.items.reduce((n,x)=>n+x.quantity,0)}</td><td>${money(s.total)}</td><td>${money(s.gross_profit)}</td><td><button class="secondary small" onclick='printReceipt(${JSON.stringify({receipt_no:s.receipt_no,created_at:s.created_at,total:s.total,gross_profit:s.gross_profit})})'>Receipt</button></td></tr>`).join(''):'<tr><td colspan="6" class="empty">No sales yet.</td></tr>'}catch(e){toast(e.message)}}
async function ask(){const q=document.getElementById('question').value.trim();if(!q)return;await askPreset(q)}
async function askPreset(q){document.getElementById('question').value=q;try{const d=await api('/api/assistant?question='+encodeURIComponent(q));const a=document.getElementById('answer');a.textContent=d.answer;a.classList.remove('hidden')}catch(e){toast(e.message)}}
async function loadReports(){try{const d=await api('/api/reports');document.getElementById('reports-body').innerHTML=d.daily.length?d.daily.map(r=>`<tr><td>${esc(r.day)}</td><td>${r.orders}</td><td>${money(r.sales)}</td><td>${money(r.gross_profit)}</td></tr>`).join(''):'<tr><td colspan="4" class="empty">No transactions to report yet.</td></tr>'}catch(e){toast(e.message)}}
function openExpense(){document.querySelector('#expense-modal form').reset();document.getElementById('e-date').value=new Date().toISOString().slice(0,10);document.getElementById('expense-modal').classList.remove('hidden')}
async function saveExpense(ev){ev.preventDefault();try{await api('/api/expenses',{method:'POST',body:JSON.stringify({category:document.getElementById('e-category').value,amount:+document.getElementById('e-amount').value,note:document.getElementById('e-note').value,expense_date:document.getElementById('e-date').value||null})});closeModal('expense-modal');toast('Expense saved');loadExpenses()}catch(e){toast(e.message)}}
async function loadExpenses(){try{const a=await api('/api/expenses');document.getElementById('expenses-body').innerHTML=a.length?a.map(x=>`<tr><td>${esc(x.expense_date)}</td><td>${esc(x.category)}</td><td>${esc(x.note)}</td><td>${money(x.amount)}</td></tr>`).join(''):'<tr><td colspan="4" class="empty">No expenses recorded.</td></tr>'}catch(e){toast(e.message)}}
async function resetDemo(){if(!confirm('Reset all sales, expenses and products to sample demo data? This cannot be undone.'))return;try{await api('/api/demo/reset',{method:'POST'});cart={};toast('Demo data restored');products=await api('/api/products');loadDashboard();loadProducts();loadHistory();loadReports();loadExpenses()}catch(e){toast(e.message)}}
function toggleTheme(){const dark=document.body.dataset.theme!=='dark';document.body.dataset.theme=dark?'dark':'light';if(dark){document.documentElement.style.setProperty('--bg','#0f172a');document.documentElement.style.setProperty('--panel','#172033');document.documentElement.style.setProperty('--ink','#e5e7eb');document.documentElement.style.setProperty('--muted','#9ca3af');document.documentElement.style.setProperty('--line','#334155')}else{location.reload()}}
(async()=>{try{products=await api('/api/products');await loadDashboard()}catch(e){toast('Cannot connect to backend: '+e.message)}})();
</script></body></html>"""
