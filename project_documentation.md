# InvestAI — Full Project Ideas & Documentation

> **Design and Evaluation of an AI-Powered Investment Assistant to Enhance Financial Literacy and Decision-Making among Beginner Investors in the Sri Lankan Stock Market**

**Degree Program:** BIT (Hons) in Network & Mobile Computing — Final Year Project Code: IT41028
**Students:** Sivasuthakaran Sanjeev (ITBNM-2211-0185) · Prabaharan Sajeevan (ITBNM-2211-0183)
**Primary Supervisor:** Mr. Isuru Samarappilige
**Co-Supervisor:** Ms. Anuradha Yapa
**Institution:** Horizon Campus, Faculty of Information Technology

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Research Aim](#2-research-aim)
3. [Research Objectives](#3-research-objectives)
4. [Research Questions](#4-research-questions)
5. [Background & Literature Review](#5-background--literature-review)
6. [Core Features](#6-core-features)
7. [Functional Requirements](#7-functional-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [Tech Stack & Architecture](#9-tech-stack--architecture)
10. [Data Requirements](#10-data-requirements)
11. [Development Methodology](#11-development-methodology)
12. [Ethics & Responsible AI](#12-ethics--responsible-ai)
13. [Evaluation Metrics](#13-evaluation-metrics)
14. [System Design Summary](#14-system-design-summary)
15. [Implementation Roadmap](#15-implementation-roadmap)
16. [References](#16-references)

---

## 1. Problem Statement

Despite increasing accessibility to the Sri Lankan stock market, beginner investors face significant challenges in making informed investment decisions due to:

- **Limited financial literacy** — most novice investors have no formal financial education
- **Fragmented, outdated resources** — existing tools are designed for experienced traders, not beginners
- **Costly advisory services** — traditional financial advisors are inaccessible to average retail investors
- **Cognitive overload** — raw market data and financial reports are complex and intimidating
- **No localised AI solution** — no comprehensive AI-powered mobile app tailored specifically for Sri Lankan beginner investors currently exists

This creates a critical gap in **financial inclusion** and widens the disparity between retail and institutional investors participating in the Colombo Stock Exchange (CSE).

---

## 2. Research Aim

To **design, develop, and evaluate** an AI-powered investment assistant that integrates:
- Agentic workflows
- Real-time market data from the CSE
- Large Language Model (LLM) reasoning

…in order to **enhance financial literacy** and **support beginner investors** in making informed, responsible investment decisions in the Sri Lankan stock market.

---

## 3. Research Objectives

### Objective 1 — Build the Assistant
Develop an AI-powered investment assistant that delivers **personalised financial education and investment guidance** tailored to beginner investors in the Sri Lankan stock market.

### Objective 2 — Evaluate Agentic Workflows
Evaluate the effectiveness of **agentic workflows combined with real-time web scraping** in generating accurate and timely investment recommendations.

### Objective 3 — Measure User Satisfaction
Assess **user satisfaction, trust, and perceived usefulness** of the AI assistant — including automated investment features — through usability testing and user feedback.

### Objective 4 — Compare Against Traditional Methods
Measure and compare the system's **technical performance** (data accuracy, response time, reliability) against traditional stock research methods.

---

## 4. Research Questions

| # | Question |
|---|----------|
| Q1 | How can the AI-powered investment assistant improve financial literacy among beginner investors in the Sri Lankan stock market? |
| Q2 | What is the effectiveness of agentic workflows combined with real-time web scraping in delivering accurate and timely investment recommendations? |
| Q3 | How do beginner investors perceive the usability, trustworthiness, perceived usefulness, and acceptance of the AI investment assistant in supporting their investment decisions? |
| Q4 | How does the AI assistant's performance in stock analysis and investment suggestion compare with traditional manual research methods in terms of accuracy and response time? |

---

## 5. Background & Literature Review

### Why AI for Investment in Sri Lanka?

The growing adoption of AI and ML in finance has transformed the global investment landscape. For emerging markets like Sri Lanka, these advances are particularly timely — a large portion of the population lacks exposure to formal financial education or accessible advisory systems.

### Key Research Findings

| Researcher | Contribution |
|------------|-------------|
| Nti, Adekoya & Weyori (2020) | Ensemble-based ML models (SVM + Genetic Algorithms) achieved up to **93.7% forecasting accuracy** for stock trends — validating AI for volatile markets like CSE |
| Ferdous & Uddin (2024) | Hybrid AI models provide more reliable forecasting than traditional statistical approaches |
| Wang (2022) | AI enables retail investors to access real-time insights previously available only to institutional players |
| Samarasinghe (2024a, 2024b) | AI assistants using NLP, LLMs, and agentic workflows bridge the gap between complex financial data and user comprehension |
| Perera (2009) & Jayasinghe (2025) | Most Sri Lankan platforms are designed for experienced traders, excluding novice investors |
| Kumar & Ranjan (2018) | Limited financial literacy continues to hinder market involvement among average Sri Lankans |
| Hossain (2014) | Big data analytics and AI can detect patterns invisible to the human eye across news, market indicators, and sentiment |
| Gedara & Nalinda (2024) | Local banks have begun implementing AI chatbots and fraud detection, showing technological readiness exists |
| S.K. Perera (2013) | Growing AI impact on the CSE, improving market transparency and investor engagement |

### The Gap
No comprehensive, AI-powered mobile application tailored specifically for **beginner investors in Sri Lanka** currently exists. Most available tools are static, lack real-time updates, and have no AI-based personalisation or automated investment guidance.

---

## 6. Core Features

### 6.1 AI Chat Assistant
- Users ask natural-language questions about stocks, market trends, and investment concepts
- Example: *"Can I invest in HNB?"* → AI fetches real-time HNB data, recent news, user risk profile, and responds in plain language
- Supports **follow-up questions** and full conversational context (multi-turn memory)
- Responds in **Tamil, Sinhala, or English** — user's choice

### 6.2 Real-Time Stock Market Data
- Scrapes the **Colombo Stock Exchange (CSE)** trade summary every 15 minutes during market hours
- Displays: price, daily change, % change, volume, market cap
- Tracks indices: ASPI, S&P SL 20
- Supports watchlist filtering — user only sees stocks they care about

### 6.3 Market News Summarisation
- Scrapes financial news from: Lanka Financial Times, Daily Mirror Business, MarketWatch, Investing.com
- AI **summarises each article** into 1–2 plain-language sentences for beginner comprehension
- Sentiment scoring (positive / neutral / negative) displayed with each article
- Semantic search: users can search "what's happening in the banking sector" and get relevant articles

### 6.4 Company & Stock Performance Explanations
- AI interprets basic financial indicators (P/E ratio, EPS, dividends) in simple language
- Explains **why a stock moved** on a given day using news + price data
- Compares stocks within the same sector

### 6.5 Beginner Learning Module
- Fundamental financial literacy content: what is a stock, how the CSE works, what is risk
- Content aligned with **OECD financial literacy guidelines**
- Short, digestible lessons integrated into the app (not a separate section)
- AI can explain concepts on-demand mid-conversation

### 6.6 Multilingual Support
- **Three languages: Tamil, Sinhala, English**
- Switch language without restarting the app
- AI responds in the same language the user writes in
- UI labels and explanations localised

### 6.7 Watchlist Management
- Add / remove CSE stocks from a personal watchlist
- Real-time price updates for watchlisted stocks
- One-tap access to AI analysis for any watchlisted stock
- Watchlist data stored securely per user account

### 6.8 Notifications & Smart Alerts
- **Investment rule alerts**: user sets a condition (e.g. "notify me if HNB drops below LKR 180")
- AI generates a plain-language explanation of why the alert fired
- Market news alerts for watchlisted stocks
- Firebase Cloud Messaging (FCM) push notifications
- Email alerts via Brevo for critical notifications
- No duplicate alerts within a 1-hour window

### 6.9 User Authentication & Profile
- Secure registration with **OTP email verification** (via Brevo)
- Login via **Supabase Auth** (JWT-based)
- Password reset via 3-step OTP flow
- Role-based access: `user` and `premium`

### 6.10 Risk Profiling & Personalised Onboarding
- On first login, user completes a risk assessment quiz (score 0–100)
- Categories: **Low / Medium / High** risk tolerance
- AI tailors all recommendations to the user's risk profile
- Onboarding adapts to financial literacy level

### 6.11 Portfolio Management
- Create named portfolios (e.g. "Long-term", "Speculation")
- Add holdings: symbol, quantity, average buy price
- Real-time **P&L calculation** (current value vs cost basis)
- AI can analyse portfolio composition and suggest improvements

### 6.12 Investment Rules Engine (Auto Invest Assistant)
- User defines rules: `price_above`, `price_below`, `change_pct_up`, `change_pct_down`, `volume_spike`
- Background agent checks rules every 15 minutes during market hours
- When triggered: creates notification + sends FCM push + AI-generated explanation
- Transparent reasoning — user always knows *why* the rule fired

### 6.13 Agentic Workflow Automation
- Background Celery workers run on schedule:
  - CSE data scraping every 15 min (market hours)
  - News scraping + sentiment analysis every 30 min
  - Investment rules check every 15 min (market hours)
  - NVIDIA NIM embedding generation after every news batch
- All agents operate independently; no manual trigger required

---

## 7. Functional Requirements

### FR-1: AI Chat Assistant
- Must allow users to ask natural-language questions about stocks and market trends
- Must generate clear, simple, beginner-friendly explanations using LLM reasoning
- Must support follow-up questions and full conversational interaction
- Must use real-time data from the DB when answering stock-specific questions

### FR-2: Real-Time Stock Market Data
- Must retrieve and display real-time stock prices from CSE via web scraping
- Users must be able to view price changes, daily performance, and basic indicators

### FR-3: Market News Summarisation
- Must collect financial news from multiple credible online sources
- AI must summarise each article into short, easy-to-understand insights
- Must display sentiment labels (positive / neutral / negative)

### FR-4: Stock Performance Explanations
- Must explain stock performance in simple language suitable for beginners
- Must interpret basic financial indicators and explain price movements

### FR-5: Beginner Learning Module
- Must provide fundamental learning materials aligned with financial literacy standards
- Content must guide users on basic investing, market behaviour, and financial terms

### FR-6: Multilingual Support
- Must support Tamil, Sinhala, and English
- Language must be switchable without restarting the application

### FR-7: Watchlist Management
- Must allow users to add or remove stocks from a personal watchlist
- Must store watchlist data securely and update it dynamically

### FR-8: Notifications & Alerts
- Must send alerts for significant stock changes, news updates, or triggered rules
- Notifications must be timely, relevant, and easy to understand

### FR-9: User Authentication
- Must include secure login with email OTP verification
- User data (watchlist, preferences, interaction history) must be stored safely

### FR-10: Agentic Workflow Automation
- Must use automated background workflows to fetch stock data, scrape news, update insights
- Agents must operate on a schedule to ensure data freshness

---

## 8. Non-Functional Requirements

### Performance
- Essential data (real-time stock prices, AI responses) must load within **3–5 seconds** under normal network conditions
- Background agents must update market data and news summaries at scheduled intervals
- AI chatbot must generate responses quickly enough to maintain smooth conversational flow

### Reliability
- System must ensure continuous availability using **fallback data sources** if primary source is unavailable
- Notifications must be delivered without duplication
- Mobile application must operate without unexpected crashes during normal usage

### Usability
- Interface must be **simple, intuitive, and beginner-friendly** with clear navigation
- All explanations must use non-technical, easy-to-understand language
- Must support Tamil, Sinhala, and English across all UI elements

### Security
- User login and authentication must protect accounts against unauthorised access
- All stored user data (watchlist, preferences) must be encrypted or securely stored
- Must comply with basic data privacy principles

### Portability
- Must operate on **Android mobile devices** (mobile-first approach)
- Must support different screen sizes and resolutions
- Architecture must allow future expansion to iOS or web

### Scalability
- Must support an increasing number of users without major performance degradation
- Architecture must allow scaling of LLM requests, background workflows, and data processing

### Maintainability
- Codebase must be **modular** — easy updates to the AI model, scraping workflows, UI components
- Documentation must be provided for core modules: AI chatbot, data pipelines, notification engine

---

## 9. Tech Stack & Architecture

### Frontend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| Mobile app | React Native (Expo) | Cross-platform iOS & Android |
| State management | Zustand | Auth state, watchlist, portfolio |
| HTTP client | Axios | API calls to FastAPI backend |
| Realtime stream | EventSource (SSE) | Streaming AI chat responses |
| Push notifications | Firebase Cloud Messaging | Investment alerts |
| Local storage | AsyncStorage | JWT token storage |

### Backend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| API framework | FastAPI (Python 3.10+) | REST API + SSE streaming |
| ORM | SQLAlchemy 2.0 | Database models |
| Migrations | Alembic | Schema version control |
| Authentication | Supabase Auth | JWT, OTP, session management |
| Task queue | Celery + Redis | Background job processing |
| Task scheduler | Celery Beat | Cron-style scheduled tasks |
| Job monitor | Flower | Celery task monitoring UI |

### AI & Intelligence
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Primary LLM | OpenRouter (Gemini Flash 1.5 / GPT-4o) | Chat reasoning, explanations, alerts |
| Embeddings | NVIDIA NIM (nv-embedqa-e5-v5, 1024-dim) | Semantic search / RAG |
| Vector search | pgvector (PostgreSQL extension) | Nearest-neighbour news retrieval |
| Sentiment | VADER + LLM summarisation | News sentiment scoring |
| Agent pattern | ReAct (Reason → Act → Observe) | Multi-step tool-using agent |

### Data & Storage
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Primary database | Supabase (PostgreSQL) | All persistent data |
| Vector store | pgvector on Supabase | News embeddings for RAG |
| File storage | Supabase Storage | Profile images, documents |
| Cache / broker | Redis | Celery broker + result backend |

### External Services
| Service | Purpose |
|---------|---------|
| Colombo Stock Exchange (cse.lk) | Real-time trade summary scraping |
| Lanka Financial Times, Daily Mirror | Local financial news scraping |
| MarketWatch, Investing.com | International news context |
| Brevo (SMTP API) | OTP emails, welcome emails, reset emails |
| Firebase FCM | Push notifications |
| Payhere | Premium subscription payments (LKR) |

### Architecture Flow
```
Mobile App (React Native)
        │
        ▼
FastAPI Backend (v1)
  ├── /auth      → Supabase Auth (JWT, OTP)
  ├── /stocks    → MarketData DB queries
  ├── /portfolio → Portfolio + Holdings
  ├── /chat      ──► AI Agent (ReAct Loop)
  │                    ├── Tools: stock data, news, portfolio, RAG search
  │                    ├── Memory: ChatSession + ChatMessage (DB)
  │                    ├── LLM: OpenRouter (Gemini / GPT-4o)
  │                    └── Embeddings: NVIDIA NIM → pgvector
  └── /notifications → Notification CRUD
        │
        ▼
Celery Workers (Redis queue)
  ├── scrape_cse_data          → every 15 min (market hours)
  ├── scrape_and_analyse_news  → every 30 min
  │     └── analyse_sentiment → VADER + LLM
  │           └── embed_news  → NVIDIA NIM → pgvector
  └── check_investment_rules  → every 15 min (market hours)
        └── FCM push + AI-generated alert message
        │
        ▼
Supabase (PostgreSQL + pgvector)
  users · user_profiles · risk_profiles
  portfolios · portfolio_holdings · investment_rules
  chat_sessions · chat_messages
  market_data · news_sentiment · price_predictions
  notifications · watchlist · otp_codes
```

---

## 10. Data Requirements

### Primary Data (collected from users)
- **Surveys & Questionnaires** — assess financial literacy levels, investment behaviour, preferences (37 participants in initial study: university students, beginner investors, general public)
- **Interviews & Focus Groups** — qualitative insights on user expectations, trust in AI recommendations, usability feedback
- **Usability Testing & Interaction Logs** — real-time monitoring during pilot and beta testing phases

### Secondary Data (automated collection)
- **CSE Trade Summary** — real-time and historical stock prices, trading volumes, indices (ASPI, S&P SL 20) scraped from cse.lk
- **Financial News** — scraped from Lanka Financial Times, Daily Mirror Business, MarketWatch, Investing.com
- **Company Annual Reports** — directly sourced from listed companies for fundamental analysis
- **Existing AI Platforms** — insights from StockGPT and CAL GPT for market context

### Data Storage Schema
```
market_data        → symbol, price, change, change_pct, volume, market_cap, recorded_at
news_sentiment     → symbol, headline, url, source, summary, sentiment_score, 
                     sentiment_label, embedding(vector 1024), published_at
price_predictions  → symbol, predicted_price, model_version, generated_at
users              → user_id (UUID), email, full_name, password_hash, role, is_email_verified
user_profiles      → full_name, age, occupation, income_level, investment_experience,
                     device_token, language
risk_profiles      → score (0-100), category (Low/Medium/High)
portfolios         → user_id, name
portfolio_holdings → portfolio_id, symbol, quantity, avg_buy_price
investment_rules   → user_id, symbol, condition_type, threshold
watchlist          → user_id, symbol
chat_sessions      → user_id, start_time, end_time, is_active
chat_messages      → session_id, sender_type, content, ai_model_used, context, timestamp
notifications      → user_id, type, message, is_read, timestamp
otp_codes          → email, otp_code, purpose, is_used, expires_at
```

---

## 11. Development Methodology

### Agile (Sprint-Based)
The project follows **Agile methodology** — iterative development in manageable sprints, each delivering a functional component. After each sprint, output is evaluated and improvements made based on user feedback.

### Sprint Plan

| Sprint | Duration | Deliverable |
|--------|----------|-------------|
| 1 | Week 1–2 | Project setup, DB schema, Supabase config, auth endpoints |
| 2 | Week 3–4 | CSE scraper, sentiment service, market data API |
| 3 | Week 5–6 | AI agent core — tools, memory, ReAct loop, OpenRouter |
| 4 | Week 7–8 | Chat router with SSE streaming, pgvector RAG |
| 5 | Week 9–10 | Celery workers — scraping pipeline, embedding pipeline |
| 6 | Week 11–12 | Investment rules engine, FCM notifications |
| 7 | Week 13–14 | React Native frontend — auth screens, dashboard, chat UI |
| 8 | Week 15–16 | Portfolio screens, watchlist, notification centre |
| 9 | Week 17–18 | Multilingual support (Tamil/Sinhala), learning module |
| 10 | Week 19–20 | Payhere payment integration, premium tier |
| 11 | Week 21–22 | Usability testing with 37+ participants, bug fixes |
| 12 | Week 23–24 | Performance benchmarking, documentation, final submission |

### Object-Oriented Design (OOD)
The system uses OOD methodology for its modular structure. Key classes:
`User` · `Stock` · `Portfolio` · `AIAgent` · `ChatSession` · `Notification` · `InvestmentRule` · `NewsArticle` · `WatchlistItem`

---

## 12. Ethics & Responsible AI

### 1. Transparency & Explainability
AI investment recommendations must be transparent. The assistant must clearly communicate *how* decisions or suggestions are made — no "black box" outputs. Users must always understand the rationale behind AI advice.

### 2. Data Privacy & Security
- Sensitive user data (investment preferences, chat history, personal info) is encrypted
- Clear policies on data ownership, consent, and third-party sharing
- Supabase RLS (Row Level Security) enforced at database level
- JWT tokens stored securely in AsyncStorage

### 3. Bias & Fairness
- AI models can inherit biases from training data or scraped sources
- Regular auditing and bias mitigation strategies incorporated
- Sentiment analysis validated against multiple sources

### 4. Accountability & Human Oversight
- System has mechanisms for human oversight
- Users can seek clarification or override automated suggestions
- Clear disclaimer: *"This is educational guidance only, not financial advice"*

### 5. Ethical Investment Practices
- AI should align with ethical investment principles
- Consider ESG (Environmental, Social, Governance) criteria
- Avoid recommending investments with clear negative social/environmental impact

### 6. User Consent & Informed Decision-Making
- Users informed about capabilities AND limitations of the AI assistant
- Informed consent obtained before data collection
- Risk profile quiz makes limitations explicit during onboarding

### 7. Stakeholder Engagement
- Ongoing engagement with users, regulators, and financial experts
- Research includes 37-participant survey + qualitative interviews
- Supervision by academic staff with industry expertise

### Ethical Approval
Research requires ethical approval due to:
- Human participant involvement (user surveys, interviews, data collection)
- Potential impact of AI-driven financial advice on novice investors

---

## 13. Evaluation Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| **Recommendation Accuracy** | % of AI-generated investment suggestions aligning with expert analysis and market outcomes | > 80% |
| **Response Time** | Average time to process user query and deliver actionable recommendation | < 3–5 seconds |
| **User Satisfaction** | Measured via post-interaction surveys and SUS (System Usability Scale) | SUS score > 70 |
| **Trust Score** | User-reported trust in AI recommendations (Likert scale) | > 4/5 average |
| **Adoption Rate** | % of registered users who return after first session | > 60% |
| **Engagement Rate** | Average number of AI chat messages per session | > 5 messages |
| **Data Freshness** | Time between CSE market update and system reflection | < 15 minutes |
| **Notification Accuracy** | % of rule alerts that correctly reflect true market conditions | > 95% |
| **System Uptime** | Availability of API and background workers | > 99% |

---

## 14. System Design Summary

### Use Cases
1. **Register & Verify** — User registers → receives OTP email → verifies → can log in
2. **Complete Risk Profile** — User answers 10-question quiz → gets Low/Medium/High rating
3. **Browse Market Data** — User opens dashboard → sees real-time CSE prices for watchlisted stocks
4. **Ask AI a Question** — User types "Should I invest in COMB?" → AI fetches data, reasons, responds
5. **Read News** — User sees AI-summarised news with sentiment badge for each article
6. **Manage Portfolio** — User adds holding → sees real-time P&L
7. **Set Investment Rule** — User sets "alert me if DIAL rises 5%" → background agent monitors
8. **Receive Notification** — Rule fires → FCM push sent → AI-written explanation in notification
9. **Switch Language** — User changes to Sinhala → entire app and AI responses switch
10. **Learn a Concept** — User asks "what is a dividend?" → AI explains in plain language

### Key Design Decisions
- **SSE streaming** for chat responses — mobile client sees tokens appear in real time, not a blank screen for 5 seconds
- **Celery Beat** for scheduling (not cron) — runs inside the Python ecosystem, restartable without data loss
- **Supabase Auth** for identity — handles JWT, refresh tokens, OTP; no custom auth implementation needed
- **pgvector on Supabase** for RAG — no separate vector DB service needed, uses existing PostgreSQL
- **NVIDIA NIM** for embeddings — higher quality financial embeddings than OpenAI text-embedding-3
- **ReAct agent pattern** — gives the LLM the ability to decide when to call tools and what to ask, rather than hardcoding logic

---

## 15. Implementation Roadmap

### What is Built (30% Complete)
- [x] FastAPI backend scaffolded with all routers
- [x] SQLAlchemy models: User, Portfolio, ChatSession, MarketData, NewsSentiment, etc.
- [x] Alembic migrations (initial schema + OTP table)
- [x] Supabase Auth integration (register, OTP verify, login, forgot password)
- [x] Brevo email service (OTP emails, welcome email, reset email)
- [x] CSE web scraper (`scraper.py`)
- [x] Celery worker base (`celery_worker.py`)
- [x] Portfolio CRUD endpoints
- [x] React Native mobile app scaffolded

### What Needs to Be Built (70% Remaining)

#### Backend — High Priority
- [ ] Fix `dependencies.py` JWT verification (must verify Supabase-signed JWTs, not self-signed)
- [ ] Implement AI agent service (`app/services/agent/`) — ✅ **built in this session**
- [ ] Implement full chat router with SSE streaming — ✅ **built in this session**
- [ ] Implement sentiment service — ✅ **built in this session**
- [ ] Implement FCM service — ✅ **built in this session**
- [ ] Wire scrape tasks to DB — ✅ **built in this session**
- [ ] Investment rules checker task — ✅ **built in this session**
- [ ] pgvector migration — ✅ **built in this session**
- [ ] Wire `/stocks` endpoints to real DB queries
- [ ] Implement `/notifications` CRUD fully
- [ ] Add watchlist router (`GET /watchlist`, `POST /watchlist`, `DELETE /watchlist/{symbol}`)
- [ ] Add risk profiling endpoint (`POST /users/risk-profile`)
- [ ] Add device token endpoint (`POST /users/device-token`)
- [ ] Payhere payment integration (`POST /payments/initiate`, `POST /payments/notify`)
- [ ] Add `.env` keys: `OPENROUTER_API_KEY`, `NVIDIA_API_KEY`, `PAYHERE_MERCHANT_ID`, `PAYHERE_MERCHANT_SECRET`

#### Frontend — React Native Screens
- [ ] Splash / Onboarding screens
- [ ] Register screen → OTP verification screen
- [ ] Login screen
- [ ] Risk profiling quiz screen (10 questions)
- [ ] Dashboard screen (real-time market data, watchlist)
- [ ] AI chat screen (SSE streaming, tool result indicators)
- [ ] News feed screen (AI summaries + sentiment badges)
- [ ] Portfolio screen (holdings, P&L, charts)
- [ ] Watchlist management screen
- [ ] Investment rules screen (set/edit/delete rules)
- [ ] Notifications screen
- [ ] Settings screen (language toggle: English / Sinhala / Tamil)
- [ ] Learning module screen
- [ ] Premium subscription screen (Payhere)

#### Infrastructure
- [ ] Run `alembic upgrade head` to apply pgvector migration
- [ ] Enable pgvector extension in Supabase dashboard
- [ ] Configure Celery Beat schedule
- [ ] Set up Redis (local or Railway)
- [ ] Configure Firebase project and get FCM server key
- [ ] Set up Payhere merchant account
- [ ] Deploy to Railway / Render

---

## 16. References

1. Nti, I. K., Adekoya, A. F., & Weyori, B. A. (2020). A systematic review of fundamental and technical analysis of stock market predictions. *Artificial Intelligence Review, 53*(4), 3007–3057.
2. Ferdous, L., & Uddin, M. (2024). Hybrid AI models for stock market forecasting: A comparative review. *Journal of Financial Innovation, 10*(2), 45–67.
3. Wang, J. (2022). Real-time AI and big data in retail investing. *Finance and Technology Review, 8*(1), 12–29.
4. Samarasinghe, R. (2024a). AI-powered investment assistants in emerging markets. *Sri Lanka Journal of Computing, 6*(3), 88–104.
5. Samarasinghe, R. (2024b). Agentic workflows for real-time financial advisory systems. *Proceedings of the Asian AI Conference*, 210–225.
6. Perera, S. (2009). Retail investor behaviour on the Colombo Stock Exchange. *Sri Lanka Economic Journal, 4*(1), 55–72.
7. Jayasinghe, M. (2025). Barriers to retail investment participation in Sri Lanka. *Ceylon Business Review, 12*(1), 33–49.
8. Kumar, R., & Ranjan, V. (2018). Financial literacy and stock market participation in developing economies. *Emerging Markets Review, 36*, 116–131.
9. Hossain, M. (2014). Big data analytics in modern finance: Opportunities and challenges. *International Journal of Financial Studies, 2*(4), 321–340.
10. Gedara, K., & Nalinda, P. (2024). AI applications in Sri Lankan banking and finance. *ICTER Proceedings 2024*, 178–190.
11. Perera, S. K. (2013). AI and market transparency on the Colombo Stock Exchange. *CSE Research Bulletin, 5*, 14–22.
12. OECD (2020). *OECD/INFE 2020 International Survey of Adult Financial Literacy*. OECD Publishing.

---

*Document generated from research proposal, methodology & design documents, and implemented codebase — InvestAI Final Year Project, Horizon Campus 2025/2026*
