from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
from typing import List
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
from datetime import datetime
import pytz

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Football Match Schedule API",
    description="API to retrieve football match schedules and broadcast channels",
    version="1.0.0"
)

# Enable CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Pydantic model for match data
class Match(BaseModel):
    day: str
    time: str
    match: str
    channels: str

# Store scraped data in memory
matches_data = []

def scrape_matches(url: str) -> List[Match]:
    try:
        # Send a GET request to the webpage
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the div with class 'inner-post-entry entry-content'
        content_div = soup.find('div', class_='inner-post-entry entry-content')
        if not content_div:
            raise HTTPException(status_code=404, detail="Content div not found")
        
        # Initialize variables
        matches = []
        current_day = ""
        
        # Find all h2 (day) and h3 (match) tags within the content div
        for element in content_div.find_all(['h2', 'h3', 'p']):
            if element.name == 'h2':
                current_day = element.get_text(strip=True)
            elif element.name == 'h3':
                match_text = element.get_text(strip=True)
                match = re.match(r'(\d{2}h\d{2})\s*–\s*(.+)', match_text)
                if match:
                    time, details = match.groups()
                    matches.append({
                        'day': current_day,
                        'time': time,
                        'match': details,
                        'channels': ''
                    })
            elif element.name == 'p' and matches and not matches[-1]['channels']:
                channels = element.get_text(strip=True)
                if channels.startswith('Canais:'):
                    matches[-1]['channels'] = channels.replace('Canais:', '').strip()
        
        return [Match(**match) for match in matches]
    
    except requests.RequestException as e:
        logger.error(f"Error fetching data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

async def scheduled_scrape():
    global matches_data
    url = os.getenv("SCRAPE_URL", "https://mantosdofutebol.com.br/guia-de-jogos-tv-hoje-ao-vivo/")
    try:
        matches_data = scrape_matches(url)
        logger.info("Scheduled scrape completed successfully")
    except Exception as e:
        logger.error(f"Scheduled scrape failed: {str(e)}")

async def log_time_until_next_scrape(scheduler):
    try:
        job = scheduler.get_job('daily_scrape')
        if job and job.next_run_time:
            next_run = job.next_run_time
            now = datetime.now(pytz.timezone("America/Sao_Paulo"))
            time_diff = next_run - now
            hours, remainder = divmod(time_diff.total_seconds(), 3600)
            minutes, seconds = divmod(remainder, 60)
            logger.info(f"Time until next scrape (1 AM): {int(hours)} hours, {int(minutes)} minutes, {int(seconds)} seconds")
        else:
            logger.warning("No scheduled scrape job found")
    except Exception as e:
        logger.error(f"Error calculating time until next scrape: {str(e)}")

@app.on_event("startup")
async def startup_event():
    global matches_data
    url = os.getenv("SCRAPE_URL", "https://mantosdofutebol.com.br/guia-de-jogos-tv-hoje-ao-vivo/")
    matches_data = scrape_matches(url)  # Initial scrape on startup
    
    # Initialize scheduler
    scheduler = AsyncIOScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        scheduled_scrape,
        trigger=CronTrigger(hour=1, minute=0),  # Run daily at 1 AM
        id='daily_scrape',
        replace_existing=True
    )
    scheduler.add_job(
        log_time_until_next_scrape,
        trigger=CronTrigger(minute=0),  # Run every hour
        args=[scheduler],
        id='log_time',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Scheduler started for daily scrape at 1 AM and hourly time logging")

@app.get("/matches", response_model=List[Match], summary="Get all matches", description="Retrieve all football matches and their broadcast channels.")
async def get_all_matches():
    if not matches_data:
        raise HTTPException(status_code=404, detail="No matches found")
    return matches_data

@app.get("/matches/{day}", response_model=List[Match], summary="Get matches by day", description="Retrieve football matches for a specific day.")
async def get_matches_by_day(day: str):
    filtered_matches = [match for match in matches_data if match.day.lower() == day.lower()]
    if not filtered_matches:
        raise HTTPException(status_code=404, detail=f"No matches found for day: {day}")
    return filtered_matches

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))  # Default to 8000 if PORT is not set
    uvicorn.run(app, host="0.0.0.0", port=port)
