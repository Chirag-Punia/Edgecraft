# Edgecraft - Bharat Seller OS

## Hackathon
- **Event:** AWS AI for Bharat Hackathon (powered by AWS, H2S innovation partner, YourStory media partner)
- **Team:** Edgecraft | Leader: Chirag Punia
- **Problem Statement:** Build an AI-powered solution that enhances decision-making, efficiency, or user experience across retail, commerce, and marketplace ecosystems.

## What We're Building
A unified retail analytics platform for Indian MSMEs that aggregates seller data from **Amazon, Flipkart, Shopify, Facebook Marketplace** into one intelligent dashboard with AI-powered insights.

### Core Value Prop
- One clear view of business: sales, inventory, shipments, pricing
- Act on AI-driven insights instead of guesswork
- AI that speaks your business in your language (multilingual - Hindi, Marathi, etc.)

## Features
1. **AI Assistant** - Natural language queries ("Why did sales drop?", "What will stockout next week?", "Summarize complaints in Marathi")
2. **Unified Dashboard** - KPIs, sales trends, order/shipment tracking
3. **Data + Ops** - Unified orders, shipments, cancellation/return tracking, inventory health (FBA + non-FBA, low stock, aging)
4. **Pricing Intelligence** - Price tracking, margin impact, price band suggestions, promo triggers, buy-box/competitor signals
5. **Customer Insights** - Feedback mining (topics, sentiment, trend alerts), product-fit insights (why ratings drop, why returns happen)
6. **Demand Forecasting** - Prevent stockouts

## User Flow
Landing Page -> Login / Sign Up -> Business Details -> Connect Marketplaces (at least one) -> Dashboard
Dashboard sections: Command Center, Orders, Shipments, Inventory, Listing, Pricing, Customer Insights, Demand Forecasting, Reports, AI Assistant, Settings, Profile Settings

## Architecture
- **Frontend:** React.js (Vite + TypeScript) with shadcn/ui components
- **Backend:** Python (FastAPI)
- **Auth:** Custom email OTP (not Auth0 as originally planned)
- **Marketplace Connect:** OAuth (Shopify/Meta/Flipkart/Amazon)
- **Data Sync:** Worker/Cron + Normalization code -> unified entities
- **Database:** MySQL (with Alembic migrations)
- **Storage:** S3 (raw payload backup + CSV/PDF exports)
- **AI:** LLM + Report Spec (JSON) + SQL templates (natural language -> safe report queries)

## Project Structure
```
Edgecraft/
├── client/              # React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── pages/       # Landing, Login, Signup, VerifyEmail, BusinessInfo, ConnectMarketplaces, Dashboard
│   │   ├── context/     # AuthContext
│   │   ├── hooks/       # useAuth
│   │   ├── lib/         # api.ts, utils.ts, constants.ts
│   │   └── types/       # TypeScript types
│   └── ...
├── server/              # FastAPI backend
│   ├── app/
│   │   ├── api/v1/      # auth, sellers, dashboard, marketplaces endpoints
│   │   ├── models/      # user, seller, marketplace_account, email_otp
│   │   ├── schemas/     # auth, seller, dashboard, marketplace
│   │   ├── services/    # auth_service, seller_service, marketplace_service, email_service
│   │   ├── core/        # security, dependencies
│   │   ├── db/          # session
│   │   └── config.py
│   ├── migrations/      # Alembic
│   └── pyproject.toml
├── ideation/            # PPT, design.md, requirements.md, wireframe PNGs
└── CLAUDE.md
```

## Conventions
- Backend API versioned under `/api/v1/`
- Pydantic schemas for request/response validation
- SQLAlchemy models with Alembic migrations
- Frontend uses shadcn/ui component library
- API client in `client/src/lib/api.ts`

## Current Status
- Auth flow implemented (signup, login, email OTP verification)
- Seller/business info collection
- Marketplace connection page
- Basic dashboard page
- Backend: auth, seller, marketplace, dashboard endpoints scaffolded

## MVP Cost Target
INR 5,200 - 10,300/month (compute + DB + storage + AI usage)

## Context Persistence
- Save session context to memory at end of every chat
- Memory location: `~/.claude/projects/-Users-chiragpunia-PycharmProjects/memory/`
