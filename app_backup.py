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

        c.executescript ("""

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
<div class="two"><div class="card"><h2>Best sellers</h2><div id="top-list"></div></div><div class="card"><h2>Recent transactions</h2><div id="recent-list"></div></div></div>

</section>

<section id="page-inventory" class="hidden"><div class="pagehead"><div><h1>Inventory</h1><div class="muted">Keep every product and stock level in control.</div></div><button onclick="openProduct()">＋ Add product</button></div>

<div class="card"><div class="toolbar"><input id="product-search" placeholder="Search name or SKU..." oninput="loadProducts()" style="flex:1;min-width:170px"><select id="category-filter" onchange="loadProducts()"><option value="">All categories</option></select><button class="secondary" onclick="document.getElementById('low-filter').checked=!document.getElementById('low-filter').checked;loadProducts()">Toggle low stock</button><input type="checkbox" id="low-filter" onchange="loadProducts()" title="Low stock only" style="width:18px"></div><div class="tablewrap"><table><thead><tr><th>Product</th><th>SKU</th><th>Category</th><th>Cost</th><th>Price</th><th>Stock</th><th>Margin</th><th>Actions</th></tr></thead><tbody id="products-body"></tbody></table></div><div class="footnote">Gross margin percentage is calculated from selling price and cost; it is not net profit.</div></div></section>

<section id="page-sales" class="hidden"><div class="pagehead"><div><h1>New sale</h1><div class="muted">Create a sale and update stock atomically.</div></div></div><div class="two"><div class="card"><h2>Choose products</h2><div class="toolbar"><input id="sale-search" placeholder="Search product..." oninput="renderSaleProducts()" style="width:100%"></div><div id="sale-products"></div></div><div class="card"><h2>Current bill</h2><div id="cart-lines" class="empty">Add products to start a bill.</div><div style="display:flex;justify-content:space-between;font-size:18px;font-weight:800;padding:15px 0;border-top:1px solid var(--line)">Total <span id="cart-total">₹0.00</span></div><button style="width:100%" onclick="checkout()">Complete sale</button><div class="footnote">Stock is checked by the server before a sale is saved.</div></div></div></section>

<section id="page-history" class="hidden"><div class="pagehead"><div><h1>Sales history</h1><div class="muted">Review receipts and recorded transactions.</div></div><a href="/api/export/sales.csv" target="_blank"><button class="secondary">↓ Export CSV</button></a></div><div class="card"><div class="tablewrap"><table><thead><tr><th>Receipt</th><th>Date</th><th>Items</th><th>Sales</th><th>Gross profit</th><th></th></tr></thead><tbody id="history-body"></tbody></table></div></div></section>

<section id="page-assistant" class="hidden"><div class="pagehead"><div><h1>Business assistant ✦</h1><div class="muted">Ask questions about your saved shop data.</div></div></div><div class="card"><h2>What would you like to know?</h2><div class="toolbar"><button class="secondary small" onclick="askPreset('Which products need restocking?')">Restock advice</button><button class="secondary small" onclick="askPreset('What were my sales today?')">Today's sales</button><button class="secondary small" onclick="askPreset('What is my inventory value?')">Inventory value</button><button class="secondary small" onclick="askPreset('Which products have highest profit?')">Profit leaders</button></div><div class="assistantbox"><input id="question" placeholder="Ask about sales, stock, profit..." onkeydown="if(event.key==='Enter')ask()"><button onclick="ask()">Ask</button></div><div id="answer" class="answer hidden"></div><div class="footnote">Offline rule-based assistant using your local database. No external AI model is connected in this version.</div></div></section>

<section id="page-reports" class="hidden"><div class="pagehead"><div><h1>Reports & insights</h1><div class="muted" id="report-period">Track performance from actual recorded transactions.</div></div><a href="/api/export/sales.csv" target="_blank"><button class="secondary">↓ Export sales CSV</button></a></div><div class="card"><div class="formgrid"><label>Start date<input id="report-start" type="date"></label><label>End date<input id="report-end" type="date"></label><div style="display:flex;align-items:end"><button onclick="loadReports()">Apply dates</button></div><div style="display:flex;align-items:end"><button class="secondary" onclick="resetReportDates()">Last 30 days</button></div></div></div><div class="stats"><div class="stat"><div class="muted">Total sales</div><div class="value" id="report-sales">₹0.00</div></div><div class="stat"><div class="muted">Orders</div><div class="value" id="report-orders">0</div></div><div class="stat"><div class="muted">Gross profit</div><div class="value" id="report-gross">₹0.00</div></div><div class="stat"><div class="muted">Expenses</div><div class="value" id="report-expenses">₹0.00</div></div><div class="stat"><div class="muted">Estimated net profit</div><div class="value" id="report-net">₹0.00</div></div></div><div class="card"><h2>Daily sales summary</h2><div class="tablewrap"><table><thead><tr><th>Date</th><th>Orders</th><th>Sales</th><th>Cost of goods</th><th>Gross profit</th></tr></thead><tbody id="reports-body"></tbody></table></div><div class="footnote">Estimated net profit = gross profit minus recorded expenses. This is an estimate, not a tax or accounting statement.</div></div><div class="card"><h2>Expenses by category</h2><div class="tablewrap"><table><thead><tr><th>Category</th><th>Total</th></tr></thead><tbody id="report-expense-categories"></tbody></table></div></div></section>

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

const days=[];for(let i=6;i>=0;i--){const dt=new Date();dt.setDate(dt.getDate()-i);const key=dt.toISOString().slice(0,10);days.push({day:key,sales:(d.daily_sales.find(x=>x.day===key)||{}).sales||0})}const max=Math.max(1,...days.map(x=>x.sales));document.getElementById('sales-chart').innerHTML=days.map(x=>\`<div class="chartcol"><b style="font-size:10px">${x.sales?money(x.sales):''}</b><div class="chartstick" style="height:${Math.max(3,x.sales/max*65)}%"></div><small>${x.day.slice(5)}</small></div>\`).join('');

const low=products.length?products.filter(p=>p.quantity<=p.reorder_level):await api('/api/products?low_stock=true');document.getElementById('low-list').innerHTML=low.length?low.slice(0,6).map(p=>\`<div style="display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid var(--line)"><div><b>${esc(p.name)}</b><div class="muted" style="font-size:11px">Threshold ${p.reorder_level}</div></div><span class="tag ${p.quantity===0?'bad':'warn'}">${p.quantity} left</span></div>\`).join(''):'<div class="empty">All products are above their reorder thresholds.</div>';

document.getElementById('top-list').innerHTML=d.top_products.length?d.top_products.map(p=>\`<div class="barrow"><span>${esc(p.name)}</span><div class="barbg"><div class="bar" style="width:${Math.min(100,p.quantity/Math.max(1,d.top_products[0].quantity)*100)}%"></div></div><span class="barval">${p.quantity} sold</span></div>\`).join(''):'<div class="empty">Record sales to see best sellers.</div>';

document.getElementById('recent-list').innerHTML=d.recent_sales.length?d.recent_sales.map(s=>\`<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--line)"><div><b>${esc(s.receipt_no)}</b><div class="muted" style="font-size:11px">${esc(s.created_at)}</div></div><b>${money(s.total)}</b></div>\`).join(''):'<div class="empty">No sales recorded yet.</div>';

}catch(e){toast(e.message)}}

function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}

async function loadProducts(){try{products=await api('/api/products?search='+encodeURIComponent(document.getElementById('product-search')?.value||'')+'&low_stock='+(document.getElementById('low-filter')?.checked||false));const cats=[...new Set(products.map(p=>p.category))].sort();const f=document.getElementById('category-filter');const old=f.value;f.innerHTML='<option value="">All categories</option>'+cats.map(x=>\`<option>${esc(x)}</option>\`).join('');f.value=cats.includes(old)?old:'';let view=products.filter(p=>!f.value||p.category===f.value);document.getElementById('products-body').innerHTML=view.length?view.map(p=>\`<tr><td><b>${esc(p.name)}</b></td><td>${esc(p.sku)}</td><td>${esc(p.category)}</td><td>${money(p.cost_price)}</td><td>${money(p.selling_price)}</td><td><span class="tag ${p.quantity<=p.reorder_level?'warn':''}">${p.quantity}</span></td><td>${p.selling_price?((p.selling_price-p.cost_price)/p.selling_price*100).toFixed(1)+'%':'—'}</td><td><button class="secondary small" onclick="editProduct(${p.id})">Edit</button> <button class="danger small" onclick="deleteProduct(${p.id})">Delete</button></td></tr>\`).join(''):'<tr><td colspan="8" class="empty">No products match your search.</td></tr>'; }catch(e){toast(e.message)}}

function openProduct(p=null){document.getElementById('product-form').reset();document.getElementById('p-id').value=p?.id||'';document.getElementById('product-modal-title').textContent=p?'Edit product':'Add product';document.getElementById('p-name').value=p?.name||'';document.getElementById('p-sku').value=p?.sku||'';document.getElementById('p-category').value=p?.category||'General';document.getElementById('p-cost').value=p?.cost_price??'';document.getElementById('p-price').value=p?.selling_price??'';document.getElementById('p-qty').value=p?.quantity??0;document.getElementById('p-reorder').value=p?.reorder_level??5;document.getElementById('p-expiry').value=p?.expiry_date||'';document.getElementById('p-supplier').value=p?.supplier||'';document.getElementById('product-modal').classList.remove('hidden')}

function closeModal(id){document.getElementById(id).classList.add('hidden')}

async function saveProduct(ev){ev.preventDefault();const id=document.getElementById('p-id').value;const payload={name:document.getElementById('p-name').value,sku:document.getElementById('p-sku').value,category:document.getElementById('p-category').value||'General',cost_price:+document.getElementById('p-cost').value,selling_price:+document.getElementById('p-price').value,quantity:+document.getElementById('p-qty').value,reorder_level:+document.getElementById('p-reorder').value,expiry_date:document.getElementById('p-expiry').value||null,supplier:document.getElementById('p-supplier').value};try{await api(id?'/api/products/'+id:'/api/products',{method:id?'PUT':'POST',body:JSON.stringify(payload)});closeModal('product-modal');toast('Product saved');await loadProducts();await loadDashboard()}catch(e){toast(e.message)}}

async function editProduct(id){try{const p=await api('/api/products');openProduct(p.find(x=>x.id===id))}catch(e){toast(e.message)}}

async function deleteProduct(id){if(!confirm('Delete this product? Products with sales history cannot be deleted.'))return;try{await api('/api/products/'+id,{method:'DELETE'});toast('Product deleted');loadProducts();loadDashboard()}catch(e){toast(e.message)}}

async function loadSaleProducts(){products=await api('/api/products');renderSaleProducts();renderCart()}

function renderSaleProducts(){const q=(document.getElementById('sale-search')?.value||'').toLowerCase();const arr=products.filter(p=>p.name.toLowerCase().includes(q)||p.sku.toLowerCase().includes(q));document.getElementById('sale-products').innerHTML=arr.map(p=>\`<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:12px 0;border-bottom:1px solid var(--line)"><div><b>${esc(p.name)}</b><div class="muted">${money(p.selling_price)} · ${p.quantity} in stock</div></div><button class="small" ${p.quantity===0?'disabled':''} onclick="addCart(${p.id})">＋ Add</button></div>\`).join('')||'<div class="empty">No products found.</div>'}

function addCart(id){const p=products.find(x=>x.id===id);if(!p)return;if((cart[id]||0)>=p.quantity){toast('Cannot add more than available stock');return}cart[id]=(cart[id]||0)+1;renderCart()}

function changeCart(id,delta){const p=products.find(x=>x.id===id);cart[id]=(cart[id]||0)+delta;if(cart[id]<=0)delete cart[id];else if(cart[id]>p.quantity){cart[id]=p.quantity;toast('Stock limit reached')}renderCart()}

function renderCart(){const entries=Object.entries(cart);document.getElementById('cart-lines').className=entries.length?'':'empty';document.getElementById('cart-lines').innerHTML=entries.length?entries.map(([id,q])=>{const p=products.find(x=>x.id===+id);return \`<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;padding:12px 0;border-bottom:1px solid var(--line)"><div><b>${esc(p.name)}</b><div class="muted">${money(p.selling_price)} each</div></div><div style="display:flex;align-items:center;gap:6px"><button class="secondary small" onclick="changeCart(${id},-1)">−</button>${q}<button class="secondary small" onclick="changeCart(${id},1)">+</button></div><b>${money(p.selling_price*q)}</b></div>\`}).join(''):'Add products to start a bill.';document.getElementById('cart-total').textContent=money(entries.reduce((sum,[id,q])=>sum+products.find(p=>p.id===+id).selling_price*q,0))}

async function checkout(){const items=Object.entries(cart).map(([product_id,quantity])=>({product_id:+product_id,quantity}));if(!items.length){toast('Add at least one product');return}try{const s=await api('/api/sales',{method:'POST',body:JSON.stringify({items})});cart={};toast('Sale complete: '+s.receipt_no);await loadSaleProducts();await loadDashboard();await loadHistory();if(confirm(\`Sale complete!**\n**Receipt: ${s.receipt_no}**\n**Total: ${money(s.total)}**\n**Gross profit: ${money(s.gross_profit)}**\n\n**Print receipt?\`)){printReceipt(s)}}catch(e){toast(e.message);await loadSaleProducts()}}

function printReceipt(s){const w=window.open('','_blank','width=420,height=650');if(!w){toast('Allow pop-ups to print the receipt');return}w.document.write(\`<html><head><title>Receipt ${esc(s.receipt_no)}</title><style>body{font:14px Arial;padding:25px}h2{text-align:center}hr{border:0;border-top:1px dashed #888}p{display:flex;justify-content:space-between}</style></head><body><h2>VyaparMate AI</h2><p style="justify-content:center">Shop sales receipt</p><hr><p><span>Receipt</span><b>${esc(s.receipt_no)}</b></p><p><span>Date</span><span>${esc(s.created_at)}</span></p><hr><p><b>Total</b><b>${money(s.total)}</b></p><p><span>Gross profit estimate</span><span>${money(s.gross_profit)}</span></p><hr><p style="justify-content:center">Thank you!</p><script>window.print()<\\/script></body></html>\`);w.document.close()}

async function loadHistory(){try{const a=await api('/api/sales');document.getElementById('history-body').innerHTML=a.length?a.map(s=>\`<tr><td><b>${esc(s.receipt_no)}</b></td><td>${esc(s.created_at)}</td><td>${s.items.reduce((n,x)=>n+x.quantity,0)}</td><td>${money(s.total)}</td><td>${money(s.gross_profit)}</td><td><button class="secondary small" onclick='printReceipt(${JSON.stringify({receipt_no:s.receipt_no,created_at:s.created_at,total:s.total,gross_profit:s.gross_profit})})'>Receipt</button></td></tr>\`).join(''):'<tr><td colspan="6" class="empty">No sales yet.</td></tr>'}catch(e){toast(e.message)}}

async function ask(){const q=document.getElementById('question').value.trim();if(!q)return;await askPreset(q)}

async function askPreset(q){document.getElementById('question').value=q;try{const d=await api('/api/assistant?question='+encodeURIComponent(q));const a=document.getElementById('answer');a.textContent=d.answer;a.classList.remove('hidden')}catch(e){toast(e.message)}}

function localDateString(date){const y=date.getFullYear();const m=String(date.getMonth()+1).padStart(2,"0");const d=String(date.getDate()).padStart(2,"0");return `${y}-${m}-${d}`}
function resetReportDates(){const end=new Date();const start=new Date();start.setDate(start.getDate()-29);document.getElementById("report-start").value=localDateString(start);document.getElementById("report-end").value=localDateString(end);loadReports()}
async function loadReports(){try{const startInput=document.getElementById("report-start");const endInput=document.getElementById("report-end");if(!startInput.value||!endInput.value){const end=new Date();const start=new Date();start.setDate(start.getDate()-29);startInput.value=localDateString(start);endInput.value=localDateString(end)}const start=startInput.value;const end=endInput.value;if(start>end){toast("Start date must be on or before end date.");return}const query=new URLSearchParams({start_date:start,end_date:end});const d=await api("/api/reports?"+query.toString());document.getElementById("report-period").textContent=`Showing ${d.start_date} to ${d.end_date}`;document.getElementById("report-sales").textContent=money(d.sales);document.getElementById("report-orders").textContent=Number(d.orders||0).toLocaleString("en-IN");document.getElementById("report-gross").textContent=money(d.gross_profit);document.getElementById("report-expenses").textContent=money(d.total_expenses);document.getElementById("report-net").textContent=money(d.estimated_net_profit);const daily=d.daily||[];document.getElementById("reports-body").innerHTML=daily.some(r=>r.orders||r.sales||r.expenses)?daily.map(r=>`<tr><td>${esc(r.day)}</td><td>${Number(r.orders||0)}</td><td>${money(r.sales)}</td><td>${money(r.cost_of_goods)}</td><td>${money(r.gross_profit)}</td></tr>`).join(""):'<tr><td colspan="5" class="empty">No transactions found for this date range.</td></tr>';const categories=d.expense_categories||[];document.getElementById("report-expense-categories").innerHTML=categories.length?categories.map(x=>`<tr><td>${esc(x.category)}</td><td>${money(x.amount)}</td></tr>`).join(""):'<tr><td colspan="2" class="empty">No expenses found for this date range.</td></tr>'}catch(e){toast("Unable to load reports: "+e.message)}}

function openExpense(){document.querySelector('#expense-modal form').reset();document.getElementById('e-date').value=new Date().toISOString().slice(0,10);document.getElementById('expense-modal').classList.remove('hidden')}

async function saveExpense(ev){ev.preventDefault();try{await api('/api/expenses',{method:'POST',body:JSON.stringify({category:document.getElementById('e-category').value,amount:+document.getElementById('e-amount').value,note:document.getElementById('e-note').value,expense_date:document.getElementById('e-date').value||null})});closeModal('expense-modal');toast('Expense saved');loadExpenses()}catch(e){toast(e.message)}}

async function loadExpenses(){try{const a=await api('/api/expenses');document.getElementById('expenses-body').innerHTML=a.length?a.map(x=>\`<tr><td>${esc(x.expense_date)}</td><td>${esc(x.category)}</td><td>${esc(x.note)}</td><td>${money(x.amount)}</td></tr>\`).join(''):'<tr><td colspan="4" class="empty">No expenses recorded.</td></tr>'}catch(e){toast(e.message)}}

async function resetDemo(){if(!confirm('Reset all sales, expenses and products to sample demo data? This cannot be undone.'))return;try{await api('/api/demo/reset',{method:'POST'});cart={};toast('Demo data restored');products=await api('/api/products');loadDashboard();loadProducts();loadHistory();loadReports();loadExpenses()}catch(e){toast(e.message)}}

function toggleTheme(){const dark=document.body.dataset.theme!=='dark';document.body.dataset.theme=dark?'dark':'light';if(dark){document.documentElement.style.setProperty('--bg','#0f172a');document.documentElement.style.setProperty('--panel','#172033');document.documentElement.style.setProperty('--ink','#e5e7eb');document.documentElement.style.setProperty('--muted','#9ca3af');document.documentElement.style.setProperty('--line','#334155')}else{location.reload()}}

(async()=>{try{products=await api('/api/products');await loadDashboard()}catch(e){toast('Cannot connect to backend: '+e.message)}})();

</script></body></html>"""
  
<div style="padding:12px;text-align:right">
  <label for="languageSelector">Choose language:</label>
  <select id="languageSelector" onchange="changeLanguage(this.value)">
    <option value="en">English</option>
    <option value="kn">ಕನ್ನಡ</option>
    <option value="hi">हिन्दी</option>
  </select>
</div>

<script>
const vyaparTranslations = {
  kn: {
    "Dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
    "Inventory": "ದಾಸ್ತಾನು",
    "New sale": "ಹೊಸ ಮಾರಾಟ",
    "Sales history": "ಮಾರಾಟದ ಇತಿಹಾಸ",
    "Business assistant": "ವ್ಯಾಪಾರ ಸಹಾಯಕ",
    "Reports & insights": "ವರದಿಗಳು ಮತ್ತು ವಿಶ್ಲೇಷಣೆ",
    "Business expenses": "ವ್ಯಾಪಾರದ ವೆಚ್ಚಗಳು",
    "Add product": "ಉತ್ಪನ್ನ ಸೇರಿಸಿ",
    "Add expense": "ವೆಚ್ಚ ಸೇರಿಸಿ",
    "Save product": "ಉತ್ಪನ್ನ ಉಳಿಸಿ",
    "Complete sale": "ಮಾರಾಟ ಪೂರ್ಣಗೊಳಿಸಿ",
    "Search name or SKU...": "ಹೆಸರು ಅಥವಾ SKU ಹುಡುಕಿ...",
    "Search product...": "ಉತ್ಪನ್ನ ಹುಡುಕಿ...",
    "Current bill": "ಪ್ರಸ್ತುತ ಬಿಲ್",
    "Total sales": "ಒಟ್ಟು ಮಾರಾಟ",
    "Gross profit": "ಒಟ್ಟು ಲಾಭ",
    "Expenses": "ವೆಚ್ಚಗಳು",
    "Save": "ಉಳಿಸಿ",
    "Cancel": "ರದ್ದುಮಾಡಿ",
    "Delete": "ಅಳಿಸಿ"
  },
  hi: {
    "Dashboard": "डैशबोर्ड",
    "Inventory": "इन्वेंटरी",
    "New sale": "नई बिक्री",
    "Sales history": "बिक्री का इतिहास",
    "Business assistant": "व्यापार सहायक",
    "Reports & insights": "रिपोर्ट और विश्लेषण",
    "Business expenses": "व्यापारिक खर्च",
    "Add product": "उत्पाद जोड़ें",
    "Add expense": "खर्च जोड़ें",
    "Save product": "उत्पाद सहेजें",
    "Complete sale": "बिक्री पूरी करें",
    "Search name or SKU...": "नाम या SKU खोजें...",
    "Search product...": "उत्पाद खोजें...",
    "Current bill": "वर्तमान बिल",
    "Total sales": "कुल बिक्री",
    "Gross profit": "सकल लाभ",
    "Expenses": "खर्च",
    "Save": "सहेजें",
    "Cancel": "रद्द करें",
    "Delete": "हटाएँ"
  }
};

const vyaparOriginalText = new WeakMap();
const vyaparOriginalPlaceholders = new WeakMap();

function changeLanguage(language) {
  const dictionary = vyaparTranslations[language] || {};

  document.querySelectorAll("body *").forEach(element => {
    if (element.id === "languageSelector") return;

    // Translate direct text only; preserve nested elements and data.
    element.childNodes.forEach(node => {
      if (node.nodeType !== Node.TEXT_NODE) return;

      if (!vyaparOriginalText.has(node)) {
        vyaparOriginalText.set(node, node.nodeValue);
      }

      const original = vyaparOriginalText.get(node);
      const key = original.trim();

      if (!key) return;

      const translated =
        language === "en" ? key : (dictionary[key] || key);

      node.nodeValue = original.replace(key, translated);
    });
  });

  document.querySelectorAll("input[placeholder], textarea[placeholder]")
    .forEach(element => {
      if (!vyaparOriginalPlaceholders.has(element)) {
        vyaparOriginalPlaceholders.set(
          element, element.getAttribute("placeholder")
        );
      }

      const original = vyaparOriginalPlaceholders.get(element);
      element.setAttribute(
        "placeholder",
        language === "en" ? original : (dictionary[original] || original)
      );
    });

  document.documentElement.lang = language;
}
</script>

<script>
(() => {
  const translations = {
    kn: {
      "Dashboard": "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್",
      "Inventory": "ದಾಸ್ತಾನು",
      "Sales": "ಮಾರಾಟ",
      "Sales History": "ಮಾರಾಟದ ಇತಿಹಾಸ",
      "Business Assistant": "ವ್ಯಾಪಾರ ಸಹಾಯಕ",
      "Reports": "ವರದಿಗಳು",
      "Expenses": "ವೆಚ್ಚಗಳು",
      "Products": "ಉತ್ಪನ್ನಗಳು",
      "Add Product": "ಉತ್ಪನ್ನ ಸೇರಿಸಿ",
      "Add Sale": "ಮಾರಾಟ ಸೇರಿಸಿ",
      "Save": "ಉಳಿಸಿ",
      "Cancel": "ರದ್ದುಮಾಡಿ",
      "Delete": "ಅಳಿಸಿ",
      "Search": "ಹುಡುಕಿ",
      "Quantity": "ಪ್ರಮಾಣ",
      "Price": "ಬೆಲೆ",
      "Stock": "ದಾಸ್ತಾನು",
      "Total": "ಒಟ್ಟು",
      "Profit": "ಲಾಭ",
      "Today": "ಇಂದು",
      "Loading...": "ಲೋಡ್ ಆಗುತ್ತಿದೆ...",
      "No data available": "ಯಾವುದೇ ಮಾಹಿತಿ ಲಭ್ಯವಿಲ್ಲ",
      "Language": "ಭಾಷೆ"
    },
    hi: {
      "Dashboard": "डैशबोर्ड",
      "Inventory": "इन्वेंटरी",
      "Sales": "बिक्री",
      "Sales History": "बिक्री का इतिहास",
      "Business Assistant": "व्यापार सहायक",
      "Reports": "रिपोर्ट",
      "Expenses": "खर्च",
      "Products": "उत्पाद",
      "Add Product": "उत्पाद जोड़ें",
      "Add Sale": "बिक्री जोड़ें",
      "Save": "सहेजें",
      "Cancel": "रद्द करें",
      "Delete": "हटाएँ",
      "Search": "खोजें",
      "Quantity": "मात्रा",
      "Price": "कीमत",
      "Stock": "स्टॉक",
      "Total": "कुल",
      "Profit": "लाभ",
      "Today": "आज",
      "Loading...": "लोड हो रहा है...",
      "No data available": "कोई जानकारी उपलब्ध नहीं है",
      "Language": "भाषा"
    }
  };

  const originalText = new WeakMap();

  function translatePage(language) {
    const dictionary = translations[language] || {};
    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT
    );

    let node;

    while ((node = walker.nextNode())) {
      if (!originalText.has(node)) {
        originalText.set(node, node.nodeValue);
      }

      const original = originalText.get(node);
      const trimmed = original.trim();

      if (!trimmed) continue;

      if (language === "en") {
        node.nodeValue = original;
      } else if (dictionary[trimmed]) {
        node.nodeValue = original.replace(
          trimmed,
          dictionary[trimmed]
        );
      }
    }

    document.querySelectorAll("[placeholder]").forEach(element => {
      if (!element.dataset.originalPlaceholder) {
        element.dataset.originalPlaceholder =
          element.getAttribute("placeholder");
      }

      const original = element.dataset.originalPlaceholder;
      element.setAttribute(
        "placeholder",
        language === "en" ? original :
          (dictionary[original] || original)
      );
    });

    document.documentElement.lang = language;
  }

  const selector = document.getElementById("languageSelector");

  if (selector) {
    selector.addEventListener("change", () => {
      translatePage(selector.value);
    });
  }

  // Translate newly added dashboard content too.
  const observer = new MutationObserver(() => {
    if (selector) translatePage(selector.value);
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true
  });
})();
</script>
                       

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
         CREATE TABLE IF NOT EXISTS sale_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
        product_id INTEGER NOT NULL REFERENCES products(id),
        quantity INTEGER NOT NULL CHECK(quantity > 0),
        price REAL NOT NULL CHECK(price >= 0),
        cost_price REAL NOT NULL DEFAULT 0,
        subtotal REAL NOT NULL CHECK(subtotal >= 0)
    );


         CREATE TABLE IF NOT EXISTS expenses(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          category TEXT NOT NULL,
          amount REAL NOT NULL CHECK(amount >= 0),
          note TEXT DEFAULT '',
          expense_date TEXT NOT NULL DEFAULT (date('now'))
        );

        """)        
