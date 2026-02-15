# Bharat Seller OS — MVP Requirements

## 1. Overview
Bharat Seller OS is a unified analytics + conversational reporting platform for Indian e-commerce sellers who sell across multiple marketplaces (Flipkart, Shopify, Meta/Facebook Commerce, Amazon). Sellers connect their marketplace accounts, we fetch operational and sales data, convert it into a standard (unified) data model, and provide dashboards and a regional-language conversational assistant that generates data-backed reports.

This document defines the MVP requirements for a small pilot release.

---

## 2. Problem Statement
Multi-marketplace sellers manage orders, inventory, pricing, and performance across separate portals and reports. Data is fragmented, insights are delayed, and many operators prefer regional languages. This leads to stockouts, pricing mistakes, slower operations, and poor decision-making.

---

## 3. Target Users
### Primary
- **MSME / SMB Sellers in India** (owner/operators, small teams)
- **D2C brands** selling on multiple channels

### Secondary
- **Agencies / account managers** managing multiple sellers (future)
- **Inventory planners / warehouse operators** (future)

---

## 4. Goals (MVP)
- **Unified data** across marketplaces in one standard model.
- **Daily insights** (KPIs + top products + basic inventory health).
- **Conversational reporting**: user asks a question; system generates a safe “report request” and returns a report with numbers.
- **Exports**: user can download reports (CSV; PDF optional).

---

## 5. Non-Goals (MVP)
- True real-time streaming (sub-minute updates).
- Automated repricing or auto-reordering execution.
- Advanced competitor scraping at scale.
- Complex multi-warehouse optimization.

---

## 6. Core Features

### 6.1 Authentication & Tenant Setup
- User can sign up / log in to the platform.
- User belongs to an **Organization (Seller)**.
- Roles (MVP): **Owner**, **Member**.

**Acceptance Criteria**
- Users can access only their organization’s data.
- Basic session management and logout.

---

### 6.2 Marketplace Connections
Sellers connect marketplace accounts via each platform’s authorization method.

**MVP connectors**
- Flipkart Seller API connection
- Shopify store connection
- Meta (Facebook/Instagram commerce assets) connection
- Amazon connection is optional for MVP (include if time permits)

**Acceptance Criteria**
- Connection status: Connected / Needs Reconnect / Error.
- Seller can disconnect a marketplace.
- Tokens/keys are stored securely (encrypted at rest).

---

### 6.3 Data Ingestion (Daily)
System fetches data daily (or 2× per day if configured) from connected marketplaces.

**Entities to fetch**
- Orders (header + line items)
- Shipments / fulfillment events
- Listings / product mapping identifiers
- Inventory (FBA-like where applicable + warehouse/location inventory where available)
- Pricing snapshots
- Sales/settlement style summaries (if available via reports)

**Acceptance Criteria**
- Each sync creates a run record with status (success/partial/failure).
- Partial failure does not corrupt existing data.
- Raw responses/reports are persisted for audit + reprocessing.

---

### 6.4 Unified Data Model
Fetched data is mapped into a standard schema to enable cross-marketplace analytics.

**Acceptance Criteria**
- Each record is linked to: `seller_id`, `marketplace`, and source identifiers.
- SKU/listing mapping supports both auto-match and manual override.

---

### 6.5 Dashboards (MVP)
A minimal dashboard provides “at a glance” performance.

**MVP widgets**
- Total sales (daily + last 7/30 days)
- Orders count
- Top products (by net sales and units)
- Basic inventory health: low stock list, days-of-cover (if computable)

**Acceptance Criteria**
- User can filter by marketplace and date range.
- Dashboard loads within acceptable time (see NFR).

---

### 6.6 Daily Insights Storage (Versioned)
Daily computed metrics are stored as “as-of” records.

**Required fields**
- `as_of_date` (business date)
- `run_id` (unique per sync/compute run)
- entity scope (e.g., seller-level, SKU-level)
- metric name/value

**Acceptance Criteria**
- Supports “last 30 days” and day-over-day comparisons.
- Re-runs do not overwrite history (new run_id).

---

### 6.7 Conversational Reporting (Pattern A)
User asks a question like:
- “Generate a report of my top performing products on Flipkart.”

System flow:
1. LLM produces a **Report Spec (JSON)** (not raw SQL).
2. Backend validates the spec (limits, allowed metrics, mandatory tenant filters).
3. Backend converts spec into parameterized SQL templates and queries the DB.
4. Results are formatted as a report + short explanation.

**Acceptance Criteria**
- No free-form SQL from the LLM is executed.
- Every query enforces tenant isolation (`seller_id`).
- If user request is ambiguous, use safe defaults and show them.

---

### 6.8 Exports
- User can export a report as **CSV** (PDF optional).
- Exported files are stored and downloadable later.

**Acceptance Criteria**
- Export includes filters used (marketplace, date range, metric).
- Export is linked to the report request and timestamp.

---

## 7. Report Types (MVP)
1. **Top Products** (metric: net sales, units)
2. **Sales by Marketplace** (daily totals)
3. **Order Status Summary** (pending/shipped/delivered/returned)
4. **Low Stock Report** (SKUs below threshold or low cover)

---

## 8. Defaults & Business Rules (MVP)
- Default time range if missing: **last 30 days**
- Default definition of sales: **shipped + delivered** (configurable later)
- Currency: INR (store raw currency and normalize where needed)
- Mask PII in UI and chat outputs.

---

## 9. Non-Functional Requirements (NFR)
- **Performance**: common dashboard/report queries ≤ 3–5 seconds for MVP data volumes.
- **Reliability**: ingestion retries; no data loss on transient errors.
- **Security**: encrypted tokens, least-privilege DB accounts, audit logs for access.
- **Scalability (MVP)**: support 5–10 sellers with daily sync under ₹10k/month infra cost.
- **Observability**: basic logs + sync run status visible in admin view.

---

## 10. Out of Scope (MVP)
- Automatic marketplace actions (repricing, cancelling orders).
- Full financial accounting / GST filings.
- Advanced ML training pipelines.

---

## 11. Milestones (Suggested)
- **Week 1**: Auth + Marketplace connect UI + token storage
- **Week 2**: Ingestion for 1 marketplace + unified schema + raw dump
- **Week 3**: Rollups + dashboard + exports
- **Week 4**: Conversational reporting (Pattern A) + 2–3 report types
