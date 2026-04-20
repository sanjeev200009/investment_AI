# run_scraper_check.py
import sys
import os
import asyncio
import logging

# Set up paths
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import SessionLocal
from app.services.scraper import scrape_and_save_cse, scrape_and_save_news

logging.basicConfig(level=logging.INFO)

async def main():
    db = SessionLocal()
    try:
        print("Checking CSE Stock Scraper...")
        stocks_saved = await scrape_and_save_cse(db)
        print(f"SUCCESS: Saved {stocks_saved} stock records to Database.")
        
        print("\nChecking News Scraper...")
        news_saved = await scrape_and_save_news(db)
        print(f"SUCCESS: Saved {news_saved} news articles to Database.")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
