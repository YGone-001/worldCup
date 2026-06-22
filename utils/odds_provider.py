import time
import requests
import config
from utils.live_provider import get_team_code

_CACHE = {}

def fetch_odds_map() -> dict:
    """Fetch odds from The Odds API and return a map keyed by 'HOME_CODE-AWAY_CODE'."""
    api_key = config.THE_ODDS_API_KEY
    if not api_key:
        return {}
        
    url = f"https://api.the-odds-api.com/v4/sports/soccer_fifa_world_cup/odds/?apiKey={api_key}&regions=eu&markets=h2h,totals"
    
    now = time.time()
    cached = _CACHE.get("the_odds_api")
    if cached and now - cached[0] < config.DATA_CACHE_TTL_SECONDS:
        return cached[1]
        
    try:
        response = requests.get(url, timeout=config.DATA_API_TIMEOUT)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error fetching The Odds API: {e}")
        return {}
        
    result = {}
    for match in data:
        home_name = match.get("home_team", "")
        away_name = match.get("away_team", "")
        
        home_code = get_team_code(home_name)
        away_code = get_team_code(away_name)
        
        if not home_code or not away_code:
            continue
            
        bookmakers = match.get("bookmakers", [])
        if not bookmakers:
            continue
            
        # Try to find a bookie with both h2h and totals, or just combine them
        home_odds = 0.0
        draw_odds = 0.0
        away_odds = 0.0
        over_2_5_odds = 0.0
        under_2_5_odds = 0.0
        
        # Iterate over bookmakers to collect best available or first available odds
        for bm in bookmakers:
            markets = bm.get("markets", [])
            for m in markets:
                key = m.get("key")
                outcomes = m.get("outcomes", [])
                if key == "h2h" and home_odds == 0:
                    for oc in outcomes:
                        name = oc.get("name")
                        price = oc.get("price")
                        if name == home_name:
                            home_odds = price
                        elif name == away_name:
                            away_odds = price
                        elif name.lower() == "draw":
                            draw_odds = price
                elif key == "totals" and over_2_5_odds == 0:
                    for oc in outcomes:
                        name = oc.get("name", "").lower()
                        price = oc.get("price")
                        point = oc.get("point")
                        if point == 2.5:
                            if name == "over":
                                over_2_5_odds = price
                            elif name == "under":
                                under_2_5_odds = price
                                
        if home_odds > 0 and draw_odds > 0 and away_odds > 0:
            match_key = f"{home_code}-{away_code}"
            market_data = {
                "home_win": home_odds,
                "draw": draw_odds,
                "away_win": away_odds
            }
            if over_2_5_odds > 0 and under_2_5_odds > 0:
                market_data["over_2_5"] = over_2_5_odds
                market_data["under_2_5"] = under_2_5_odds
                
            result[match_key] = market_data
            
    _CACHE["the_odds_api"] = (now, result)
    return result
