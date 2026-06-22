import os
import json
import requests
import datetime
from config import THE_ODDS_API_KEY, DATA_DIR

TEAM_NAME_MAP = {
    "USA": "USA", "United States": "USA",
    "Australia": "AUS",
    "France": "FRA",
    "Senegal": "SEN",
    "Iraq": "IRQ",
    "Norway": "NOR",
    "Argentina": "ARG",
    "Algeria": "ALG",
    "Austria": "AUT",
    "Jordan": "JOR",
    "Portugal": "POR",
    "DR Congo": "COD", "Congo DR": "COD", "Democratic Republic of the Congo": "COD",
    "England": "ENG",
    "Croatia": "CRO",
    "Ghana": "GHA",
    "Panama": "PAN",
    "Uzbekistan": "UZB",
    "Colombia": "COL",
    "Czech Republic": "CZE", "Czechia": "CZE",
    "South Africa": "RSA",
    "Switzerland": "SUI",
    "Bosnia and Herzegovina": "BIH", "Bosnia": "BIH",
    "Canada": "CAN",
    "Qatar": "QAT",
    "Mexico": "MEX",
    "South Korea": "KOR", "Korea Republic": "KOR",
    "Scotland": "SCO",
    "Morocco": "MAR",
    "Brazil": "BRA",
    "Haiti": "HAI",
    "Turkey": "TUR", "Türkiye": "TUR",
    "Paraguay": "PAR",
    "Netherlands": "NED",
    "Sweden": "SWE",
    "Germany": "GER",
    "Ivory Coast": "CIV", "Côte d'Ivoire": "CIV"
}

def get_team_code(name):
    return TEAM_NAME_MAP.get(name)

def fetch_and_update_odds():
    if not THE_ODDS_API_KEY:
        print("[Error] THE_ODDS_API_KEY not found in .env or config.")
        return False
        
    sport_key = "soccer_fifa_world_cup"
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds/?apiKey={THE_ODDS_API_KEY}&regions=eu&markets=h2h"
    
    print(f"Fetching from The Odds API: {sport_key} ...")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[API Error] Could not fetch live odds: {e}")
        # If FIFA World Cup is not active, odds API might return 404 for this sport. 
        # In a real scenario, we might fallback to generic upcoming soccer if we really wanted to test.
        if isinstance(e, requests.exceptions.HTTPError) and response.status_code == 404:
            print("Note: The 'soccer_fifa_world_cup' market is currently not active on The Odds API.")
            print("To test the API logic, you can change the sport_key to an active league like 'soccer_epl'.")
        return False

    if not data:
        print("[Info] The Odds API returned an empty list (no odds currently available for this sport).")
        return False

    # Process data into a map: (home_code, away_code) -> odds dict
    odds_map = {}
    for match in data:
        home_name = match.get('home_team')
        away_name = match.get('away_team')
        
        home_code = get_team_code(home_name)
        away_code = get_team_code(away_name)
        
        if not home_code or not away_code:
            continue
            
        bookmakers = match.get('bookmakers', [])
        if not bookmakers:
            continue
            
        # Prioritize Pinnacle or use the first one available
        bookie = next((b for b in bookmakers if b['key'] == 'pinnacle'), bookmakers[0])
        
        h2h_market = next((m for m in bookie.get('markets', []) if m['key'] == 'h2h'), None)
        if not h2h_market:
            continue
            
        outcomes = h2h_market.get('outcomes', [])
        
        home_odds = draw_odds = away_odds = 0.0
        for out in outcomes:
            name = out.get('name')
            price = out.get('price')
            if name == home_name:
                home_odds = price
            elif name == away_name:
                away_odds = price
            elif name.lower() == 'draw':
                draw_odds = price
                
        if home_odds > 0 and draw_odds > 0 and away_odds > 0:
            odds_map[f"{home_code}_{away_code}"] = {
                "home_win": home_odds,
                "draw": draw_odds,
                "away_win": away_odds
            }

    if not odds_map:
        print("[Info] Fetched odds, but no matching teams found in our database.")
        return False
        
    print(f"[Success] Extracted {len(odds_map)} match odds from API.")

    # Now update schedule.json
    schedule_path = os.path.join(DATA_DIR, "schedule.json")
    try:
        with open(schedule_path, 'r', encoding='utf-8') as f:
            sched = json.load(f)
            
        updated_count = 0
        for m in sched.get('matches', []):
            key = f"{m['home']}_{m['away']}"
            if key in odds_map:
                m['odds'] = odds_map[key]
                m['odds_source'] = 'The Odds API (Live)'
                m['odds_updated_at'] = datetime.datetime.now().isoformat()
                updated_count += 1
                
        with open(schedule_path, 'w', encoding='utf-8') as f:
            json.dump(sched, f, ensure_ascii=False, indent=2)
            
        print(f"[Success] Updated {updated_count} matches in schedule.json with live odds!")
        return True
    except Exception as e:
        print(f"[Error] Failed to update schedule.json: {e}")
        return False
