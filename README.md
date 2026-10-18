# VyaparMate AI

A locally runnable MVP for Indian small retailers. It includes a responsive web dashboard, product inventory, point-of-sale sales recording, SQLite persistence, low-stock alerts, daily reports, CSV export, expenses, and an offline rule-based business assistant.

## Requirements
- Windows 10/11
- Python 3.11 or newer
- Internet for the first dependency installation only

## Quick start
1. Extract this folder to `C:\Users\yashu\OneDrive\Desktop\VyaparMate-AI` (or another folder).
2. Double-click `run.bat`.
3. Wait until Uvicorn reports that the application is running.
4. Open http://127.0.0.1:8000
5. API docs: http://127.0.0.1:8000/docs
6. Health check: http://127.0.0.1:8000/health

The app creates `vyaparmate.db` beside `app.py`. The database is persistent and is not committed to source control.

## Manual start
Open PowerShell in this folder:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload --port 8000
```
If PowerShell blocks activation, use `run.bat`, or run `.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.venv\Scripts\python.exe -m uvicorn app:app --port 8000`.

## Features
- Product create/edit/delete, search, category filtering and low-stock view
- Sales cart, stock checks, atomic stock deduction, receipt and sale history
- Dashboard metrics and seven-day chart
- Offline assistant queries for sales, inventory, restocking, and profit leaders
- Daily report table and CSV sales export
- Business expense recording
- Sample kirana shop data
- Confirmed reset of demo data

## Important limitations
- The assistant is rule-based and offline; no external AI model is connected.
- This is a hackathon/demo MVP, not a production accounting, GST invoicing, payment, or multi-user system.
- Authentication, supplier purchase orders, expiry notifications, advanced date filters, and production deployment controls are not implemented in this starter.
- Gross profit is recorded sales minus the saved cost of goods; it excludes operating expenses, taxes, returns, and other accounting adjustments.
- The reset endpoint is intended only for local demo use. Do not expose this app publicly without authentication and security hardening.

## Suggested 3-minute demo
1. Open dashboard and explain sales, inventory valuation, and low-stock alerts.
2. Open Inventory and add a sample product.
3. Open New Sale, add items, complete a sale, and show stock decrement.
4. Ask the assistant which products need restocking.
5. Open Sales History and Reports, then export the sales CSV.
6. Record an expense and explain the local SQLite persistence.

## Data and privacy
The application stores data in a local SQLite file on the computer. There is no external AI call or cloud upload in this version. Protect the computer and database file as you would any business data.
