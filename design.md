# Bharat Seller OS — MVP Design

## 1. System Summary
The system connects to seller marketplaces, ingests data on a schedule, standardizes it into unified entities in a relational database, computes daily rollups/insights, and supports a conversational assistant that generates **Report Specs** (JSON) which are validated and compiled into safe SQL templates.

Key design constraints:
- Store unified entities in **one SQL database** (MySQL or Postgres).
- Store raw payloads and exports in **object storage** (S3).
- No heavy analytics stack (no Glue/Redshift). Metrics and forecasting are computed by application code.
- Conversational AI uses **Pattern A**: Spec → validated SQL templates.

---

## 2. High-Level Architecture
### Components
1. **Web/App UI**
   - Dashboards + Chat (regional language toggle)
   - Marketplace connection screens
2. **App Backend**
   - Auth, tenant management, APIs
   - Report generation endpoint
3. **Connector/Sync Worker**
   - Scheduled jobs (daily / configurable)
   - Pull marketplace data; write raw dumps + normalized records
4. **Unified SQL Database**
   - Canonical entities + rollups/insights
5. **Object Storage (S3)**
   - Raw marketplace payloads/reports
   - Exported report files
6. **AI Orchestrator (Backend Module)**
   - Calls LLM to generate Report Spec
   - Validates and executes report requests

---

## 3. Data Flow
### A) Marketplace Sync
1. Scheduler triggers sync for each connected account.
2. Connector fetches incremental data (using cursor/last-sync markers).
3. Save **raw payload/report** to S3 (audit/replay).
4. Normalize to unified entities and upsert into SQL DB.
5. Compute daily rollups and write to insights tables.

### B) Conversational Report
1. User asks a question in chat.
2. Backend passes context + metrics catalog to LLM.
3. LLM returns a **Report Spec JSON**.
4. Backend validates spec (tenant, allowed metrics, max limits).
5. Backend compiles spec to parameterized SQL templates.
6. DB query runs under read-only role; results returned.
7. Backend formats report; optional short LLM summary based only on returned data.
8. Optional export generated and saved to S3.

---

## 4. Unified Data Model (MVP)
### Core tables (canonical entities)
- `sellers` (organization/tenant)
- `users`, `roles`
- `marketplace_accounts` (per seller + marketplace)
- `product_master` (internal product identity)
- `listing_map` (marketplace listing/SKU/ASIN → product_master)
- `orders` (header)
- `order_items` (line items)
- `shipments` + `shipment_events`
- `inventory_snapshots` (by sku/listing, location, timestamp)
- `price_snapshots` (by listing, timestamp)
- `returns_refunds` (optional in MVP if available)

### Daily insights tables
Option A (simple): single table
- `daily_insights`:
  - `seller_id`, `marketplace`, `as_of_date`, `run_id`
  - `entity_type` (SELLER/SKU/CHANNEL)
  - `entity_id` (nullable for SELLER-level)
  - `metric_name`, `metric_value`
  - `created_at`, `is_latest`

Option B (preferred for speed): history + current
- `daily_insights_history` (append-only, all runs)
- `daily_insights_current` (latest per seller/marketplace/date/entity/metric)

**Why include `as_of_date`:** it represents the business day of the metric and supports backfills/reruns without confusion.

---

## 5. Ingestion & Normalization
### Strategy
- **Incremental pulls** where supported (time-based cursor, order updated timestamps).
- Store `sync_state` per marketplace_account:
  - last_successful_sync_at
  - last_cursor/token/report_id

### Idempotency
- Use unique constraints on external IDs:
  - `external_order_id + marketplace + marketplace_account_id`
- Upsert behavior:
  - order status updates overwrite current status but also append to status history if required.

### Raw Dump (S3) layout (example)
- `raw/{seller_id}/{marketplace}/{entity}/{yyyy}/{mm}/{dd}/{run_id}.json`
- `exports/{seller_id}/{report_type}/{timestamp}/report.csv`

---

## 6. Metrics Engine (Code)
### Approach
- Compute rollups after each sync run (or nightly):
  - `sku_channel_daily` (sales units/net_sales per day)
  - `marketplace_daily` (sales per marketplace per day)
  - `inventory_health_current` (latest stock, days cover)
- Store rollups in DB for fast chat/report queries.

### Benefits
- Chat queries avoid scanning large order_items repeatedly.
- Supports the “under ₹10k/month MVP” goal.

---

## 7. Conversational AI Design (Pattern A)
### 7.1 Report Spec JSON (MVP)
Example:
```json
{
  "report_type": "top_products",
  "marketplace": "flipkart",
  "metric": "net_sales",
  "time_range": { "type": "last_n_days", "n": 30 },
  "group_by": ["product_id"],
  "filters": {},
  "limit": 10,
  "format": "table"
}
