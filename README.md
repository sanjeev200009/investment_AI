# InvestAI

An AI-powered, educational investment assistant for beginner investors on the
Colombo Stock Exchange (CSE). Final-year project, BIT (Hons) Network & Mobile
Computing, Horizon Campus.

| Part | Stack |
|---|---|
| `investai-backend/` | FastAPI, SQLAlchemy + Alembic on Supabase Postgres (pgvector), Supabase Auth (JWT via JWKS), Celery + Redis, NVIDIA NIM with OpenRouter failover, Brevo email, Firebase Cloud Messaging |
| `investai-mobile/` | React Native (Expo SDK 54), React Navigation, Zustand, axios + SSE streaming chat |

InvestAI is educational. It never places trades and never tells a user to buy
or sell; the assistant's system prompt and every AI surface enforce that.

## Run locally

### Backend

```bash
cd investai-backend
python -m venv venv && venv/Scripts/activate   # Windows; use venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env                            # then fill in the values
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

- Every route is under `/api/v1`. Interactive docs: `http://localhost:8000/docs` (development only).
- `GET /health` checks the database too and returns 503 if it is unreachable.
- Tests are offline and read-only: `python -m pytest`.

Background jobs (market scrapes, news, rule alerts, daily snapshots) need Redis:

```bash
celery -A celery_worker.celery_app worker --loglevel=info -Q default --pool=solo
celery -A celery_worker.celery_app beat --loglevel=info
```

`--pool=solo` is for Windows only. Beat times are Asia/Colombo.

### Mobile

```bash
cd investai-mobile
npm install
cp .env.example .env    # EXPO_PUBLIC_API_BASE_URL=http://<your LAN IP>:8000/api/v1
npx expo start
```

Push notifications need a development or EAS build (not Expo Go) and a
`google-services.json` from Firebase next to `app.json` (gitignored).

## Deploy

### Backend: one free Oracle Cloud VM

The whole backend runs on an Oracle Cloud Always Free VM with Docker Compose:
FastAPI, Celery worker, Celery Beat, Redis and Flower, with Caddy providing
HTTPS. It is the architecture in the proposal, unchanged. Supabase stays the
database and auth provider.

Step-by-step guide: **[deploy/README.md](deploy/README.md)**. In short:

```bash
curl -fsSL https://raw.githubusercontent.com/sanjeev200009/investment_AI/main/deploy/setup.sh | bash
cd ~/investment_AI/deploy && docker compose up -d --build
```

The same image also runs on any Docker or Procfile host (`investai-backend/Dockerfile`,
`investai-backend/Procfile`). Off the VM, set `FIREBASE_CREDENTIALS_JSON` to the
service-account JSON itself instead of mounting a key file.

`python -m scripts.run_jobs market|news|daily` runs the scheduled jobs once by
hand, without Redis, which is useful for testing.

### Mobile (Android)

Push notifications need `google-services.json` (Firebase project
`investai-33294`, package `lk.investai.mobile`) and a real build, not Expo Go.
See section 6 of [deploy/README.md](deploy/README.md). A release build refuses to
start without `EXPO_PUBLIC_API_BASE_URL`, on purpose. The package id becomes
permanent once the first build is uploaded to a store.

## Project documents

- `project_documentation.md` — research aim, requirements and design.
- `HANDOVER.md`, `INVESTIGATION_REPORT.md`, `investai-backend/docs/REMEDIATION_LOG.md` — audit history.
