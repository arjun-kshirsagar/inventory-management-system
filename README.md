# Clothing Store Inventory Management System

A monorepo for running a clothing store. It handles:
- a catalog where stock is tracked per **size × colour variant**
- receiving stock from suppliers
- a barcode-driven **point of sale**
- **Indian GST invoices** and credit notes
- reports for the owner

| Path | Stack |
|---|---|
| `backend/` | FastAPI · SQLAlchemy 2 · PostgreSQL · Alembic · WeasyPrint (PDFs) |
| `frontend/` | Next.js 16 (App Router) · TypeScript · Tailwind CSS 4 · TanStack Query · Recharts |

## Quick start

**With Docker:**

```bash
docker compose up --build
docker compose exec backend python -m app.seed --demo   # optional demo catalog + 30 days of sales
```

**Locally** (needs Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 22 and PostgreSQL 16):

```bash
make install
make db            # or point DATABASE_URL in backend/.env at your own Postgres
make migrate demo  # schema + admin user + demo data
make dev           # API on :8000, web app on :3000
```

Open http://localhost:3000. API docs are at http://localhost:8000/docs.

| Login | Password | Role |
|---|---|---|
| `admin@store.local` | `admin123` | Admin |
| `cashier@store.local` | `cashier123` | Cashier (demo data only) |

Change these, and set `JWT_SECRET`, before using this for real. See `backend/.env.example`.

## What each role can do

| | Admin | Cashier |
|---|:-:|:-:|
| POS: sell, look up customers, print invoices | ✓ | ✓ |
| View sales, process returns / exchanges | all sales | own sales |
| Browse products and stock; receive stock (GRN) | ✓ | ✓ |
| Create/edit products and prices, CSV import, stock adjustments | ✓ | |
| Dashboard and reports | ✓ | |
| Store details, GST rates, users | ✓ | |

The API enforces these rules. The UI only hides what a role can't use.

## How it works

### Catalog
A **product** is something like "Slim Fit Oxford Shirt", with an HSN code, brand and category. Each **variant** is one size × colour combination, and each has:
- its own SKU (`P00001-M-BLU`)
- an EAN-13 barcode in the GS1 in-store range (`200…`)
- its own MRP, selling price, cost price and reorder level

You can generate a whole size/colour grid in one step, import products from CSV, and print barcode labels as a PDF.

### Stock
`product_variants.quantity_on_hand` can only change through `backend/app/services/stock.py`. Every change:
- locks the row (`SELECT … FOR UPDATE`, always in id order to avoid deadlocks)
- refuses to go below zero
- writes a row to the append-only `stock_movements` ledger: purchase, sale, return or adjustment

If two tills try to sell the last unit at the same moment, one succeeds and the other gets "insufficient stock". A test covers this.

### GST
- **Prices include GST**, as is normal for clothing in India. The taxable value is worked backwards: `price × 100 / (100 + rate)`.
- **Rates live in the `tax_slabs` table**, not in code. A product's HSN code matches the longest prefix rule that is in effect on the sale date.
- **Apparel (HSN 61/62) and footwear (64) are seeded at 5% up to ₹2,500 per piece and 18% above.** These are the rates from the 22 Sept 2025 change. The test is the per-piece value after discount, so a discount can move an item into the lower slab.
- When a rate changes, add a new rule with a later "effective from" date. Old invoices keep the rate they were issued with.
- **Place of supply** is the customer's state, or the store's state for walk-in customers. Same state means CGST + SGST; a different state means IGST.
- **Rounding:** each line is rounded half-up to the paisa, and the bill total is rounded to the nearest rupee (shown as "round off").

### Invoices
- **Numbering** is `INV/2026-27/000001`, consecutive with no gaps within each Indian financial year (April–March). The numbers come from a row-locked counter rather than a Postgres sequence, because sequences skip numbers when a transaction rolls back.
- **Sale snapshot:** each sale stores the product name, size, colour, HSN, price and cost at the time of sale, so editing the catalog later never changes old invoices.
- **Double-click safety:** checkout sends an idempotency key, so a double-click can't create two sales.
- **Formats:** an A4 tax invoice with an HSN/rate tax breakdown and the amount in words, an 80 mm thermal receipt, and credit notes for returns.

### Returns
Returns can be partial. Each return gets its own credit note number, and you choose per item whether it goes back into stock. When the last unit of a line is returned, it gets whatever amount is left on that line, so all the refunds for a line add up exactly to what was charged. For an exchange, process a return and then make a new sale.

### Reports (admin)
Most reports take a date range, and each section exports to CSV.
- **Dashboard:** today's sales, bills and average bill, plus a 30-day trend and a reorder list.
- **Sales:** by day, category, brand, cashier, size or colour, plus totals by payment method. Figures are net of returns.
- **Best sellers and slow movers**, plus **sell-through by size and colour**, to show which sizes sell out first.
- **Stock valuation** by category, at cost, selling price and MRP.
- **Low stock**, with a suggested reorder quantity.
- **GST summary:** HSN-wise outward supplies and credit notes (GSTR-1 tables 12 and 9B), split into intra-state and inter-state.
- **Profit:** revenue excluding GST, minus the cost recorded at the time of sale.

## Development

```bash
make test      # backend pytest suite (uses an `ims_test` database; see backend/tests/conftest.py)
make lint      # ruff + eslint + tsc
make e2e       # Playwright: create product → receive stock → sell → invoice → reports
make gen-api   # regenerate frontend/src/lib/api/schema.d.ts after changing API schemas
cd backend && uv run alembic revision --autogenerate -m "..."   # after changing models
```

The frontend talks to the API through a Next.js rewrite (`/api/*` → `API_URL`), so the refresh-token cookie is first-party. The access token is held only in memory. When a request gets a 401, the client refreshes the token once and retries.

### Layout

```
backend/app/
  api/v1/      routers: auth, users, catalog, inventory, customers, sales, reports, settings
  services/    business logic: stock, sales, gst, numbering, reports, documents, catalog
  models/      SQLAlchemy models
  schemas/     Pydantic request/response models
  templates/   invoice, receipt, credit note and label HTML (rendered to PDF)
frontend/src/
  app/(app)/   dashboard, pos, sales, products, inventory, reports, settings
  components/  UI building blocks and feature components
  lib/         typed API client, auth context, formatting, hooks
```
