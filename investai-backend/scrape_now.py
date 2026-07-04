import asyncio
from app.database import SessionLocal
from app.services.scraper import scrape_and_save_cse, scrape_and_save_news

async def main():
    db = SessionLocal()
    print('Scraping market data...')
    await scrape_and_save_cse(db)
    print('Scraping news...')
    await scrape_and_save_news(db, None)
    print('Scraping complete.')
    db.close()

if __name__ == '__main__':
    asyncio.run(main())
