#!/usr/bin/env bash

set -e

# Create directories
mkdir -p investai-backend/app/models
mkdir -p investai-backend/app/routers
mkdir -p investai-backend/app/services
mkdir -p investai-backend/app/schemas
mkdir -p investai-backend/app/utils
mkdir -p investai-backend/tests

# Create top-level files
touch investai-backend/celery_worker.py
touch investai-backend/requirements.txt
touch investai-backend/.env

# Create app files
touch investai-backend/app/main.py
touch investai-backend/app/config.py
touch investai-backend/app/database.py

# Create model files
touch investai-backend/app/models/user.py
touch investai-backend/app/models/stock.py
touch investai-backend/app/models/portfolio.py
touch investai-backend/app/models/chat.py
touch investai-backend/app/models/notification.py

# Create router files
touch investai-backend/app/routers/auth.py
touch investai-backend/app/routers/stocks.py
touch investai-backend/app/routers/chat.py
touch investai-backend/app/routers/portfolio.py
touch investai-backend/app/routers/notifications.py

# Create service files
touch investai-backend/app/services/ai_agent.py
touch investai-backend/app/services/scraper.py
touch investai-backend/app/services/sentiment.py
touch investai-backend/app/services/fcm.py

# Create package marker files
touch investai-backend/app/schemas/__init__.py
touch investai-backend/app/utils/__init__.py

echo "Scaffold created under investai-backend/"
