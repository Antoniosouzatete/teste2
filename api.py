from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import re
from typing import List
import os

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
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

@app.on_event("startup")
async def startup_event():
    global matches_data
    url = os.getenv("SCRAPE_URL", "https://mantosdofutebol.com.br/guia-de-jogos-tv-hoje-ao-vivo/")
    matches_data = scrape_matches(url)

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
