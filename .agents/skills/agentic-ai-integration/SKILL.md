---
name: agentic-ai-integration
description: Reference guide for the Agentic AI files, tasks, and configurations inside investai-backend.
---

# Agentic AI Integration Reference

This skill documents the AI agent backend architecture implemented in `investai-backend`. Use this as a reference whenever working on the backend agent logic.

## Core Agent Components (`app/services/agent/`)
- `__init__.py`: Initialization for the agent module.
- `tools.py`: Tools definitions for the AI agent (e.g., scraping, database retrieval).
- `embeddings.py`: Logic for creating and querying vector embeddings using pgvector.
- `memory.py`: Manages the conversational context and short-term/long-term memory of the agent.

## Integrated Services & Routers
- `app/routers/chat.py`: Exposes the AI chat endpoints.
- `app/services/sentiment.py`: Sentiment analysis module for market sentiment.
- `app/services/fcm.py`: Firebase Cloud Messaging integration for AI alerts.

## Background Tasks (Celery)
- `celery_worker.py`: The main Celery application configuring the worker and beat schedulers.
- `tasks/scrape_tasks.py`: Scheduled tasks for scraping financial data.
- `tasks/rules_tasks.py`: Scheduled tasks for evaluating user alerts and rules.

## Setup Requirements
1. **Migrations**: `alembic upgrade head` applies pgvector and agent schemas (e.g. `a1b2c3d4e5f6_add_pgvector_and_agent_schema.py`).
2. **Environment Variables**:
   - `OPENROUTER_API_KEY`: API key from OpenRouter.ai
   - `NVIDIA_API_KEY`: API key for NVIDIA NIM/build.nvidia.com
3. **Workers**: Requires a running Celery worker (`celery -A celery_worker worker`) and Celery beat scheduler (`celery -A celery_worker beat`) alongside the FastAPI server.

## Reference Source Files
The complete set of original source files for this agent implementation are stored locally in this skill's `references/` directory. If you ever need to restore, inspect, or understand the underlying implementation of any of the components listed above, you can read the files from `.agents/skills/agentic-ai-integration/references/`.
