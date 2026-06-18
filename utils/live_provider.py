import time
from datetime import datetime, timedelta
from typing import Any

import requests

import config


TEAM_NAME_TO_CODE = {
    "United States": "USA", "USA": "USA",
    "Turkey": "TUR",
    "Mali": "MLI",
    "Trinidad and Tobago": "TTO", "Trinidad": "TTO",
    "Argentina": "ARG",
    "Japan": "JPN",
    "Senegal": "SEN",
    "Jamaica": "JAM",
    "France": "FRA",
    "Nigeria": "NGA",
    "Honduras": "HON",
    "Saudi Arabia": "KSA",
    "Brazil": "BRA",
    "South Korea": "KOR",
    "Cameroon": "CMR",
    "Ecuador": "ECU",
    "Spain": "ESP",
    "Uzbekistan": "UZB",
    "Chile": "CHL",
    "Canada": "CAN",
    "England": "ENG",
    "Colombia": "COL",
    "Egypt": "EGY",
    "Bolivia": "BOL",
    "Germany": "GER",
    "Iran": "IRN",
    "New Zealand": "NZL",
    "Ghana": "GHA",
    "Portugal": "POR",
    "Mexico": "MEX",
    "Australia": "AUS",
    "Scotland": "SCO",
    "Netherlands": "NED",
    "Qatar": "QAT",
    "Switzerland": "SUI",
    "Costa Rica": "CRC",
    "Serbia": "SRB",
    "Belgium": "BEL",
    "Uruguay": "URU",
    "Tunisia": "TUN",
    "China": "CHN",
    "Italy": "ITA",
    "Morocco": "MAR",
    "Paraguay": "PAR",
    "Indonesia": "IDN",
    "Croatia": "CRO",
    "Denmark": "DEN",
    "Algeria": "ALG",
    "Panama": "PAN",
    # Additional teams:
    "Czech Republic": "CZE", "Czechia": "CZE",
    "South Africa": "RSA",
    "Bosnia and Herzegovina": "BIH", "Bosnia & Herzegovina": "BIH",
    "Haiti": "HAI",
    "Norway": "NOR",
    "Iraq": "IRQ",
    "Sweden": "SWE",
    "Austria": "AUT",
    "Jordan": "JOR",
    "Democratic Republic of the Congo": "COD", "DR Congo": "COD",
    "Ivory Coast": "CIV",
    "Curaçao": "CUW",
    "Cape Verde": "CPV"
}


def get_team_code(name: str) -> str:
    if not name:
        return ""
    cleaned = name.strip()
    if cleaned in TEAM_NAME_TO_CODE:
        return TEAM_NAME_TO_CODE[cleaned]
    for k, v in TEAM_NAME_TO_CODE.items():
        if k.lower() == cleaned.lower():
            return v
    return cleaned[:3].upper()


def parse_worldcup26_date(local_date_str: str) -> tuple[str, str]:
    # local_date is like "06/13/2026 21:00"
    try:
        dt = datetime.strptime(local_date_str.strip(), "%m/%d/%Y %H:%M")
        return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")
    except Exception:
        parts = local_date_str.strip().split()
        if len(parts) >= 2:
            date_part = parts[0]
            time_part = parts[1][:5]
            date_subparts = date_part.split("/")
            if len(date_subparts) == 3:
                return f"{date_subparts[2]}-{date_subparts[0]:>02}-{date_subparts[1]:>02}", time_part
        return "", "00:00"


def normalize_worldcup26_match(raw: dict) -> dict:
    home_name = raw.get("home_team_name_en", "")
    away_name = raw.get("away_team_name_en", "")
    home_code = get_team_code(home_name)
    away_code = get_team_code(away_name)
    
    date_str, time_str = parse_worldcup26_date(raw.get("local_date", ""))
    
    group_val = raw.get("group", "")
    if group_val and len(group_val) == 1:
        group_val = f"Group {group_val}"
    
    match = {
        "id": f"wc26-{raw.get('id', '')}",
        "date": date_str,
        "time": time_str,
        "group": group_val or "世界杯",
        "home": home_code,
        "away": away_code,
        "round": int(raw.get("matchday", 1)),
        "venue": "",
    }
    match["home_name"] = home_name or home_code
    match["away_name"] = away_name or away_code
    
    if raw.get("finished") == "TRUE":
        try:
            match["score"] = {
                "ft": [int(raw.get("home_score", 0)), int(raw.get("away_score", 0))]
            }
        except (ValueError, TypeError):
            pass
            
    return match


def normalize_openfootball_match(raw: dict) -> dict:
    home_name = raw.get("team1", "")
    away_name = raw.get("team2", "")
    home_code = get_team_code(home_name)
    away_code = get_team_code(away_name)
    
    date_str = raw.get("date", "")
    time_raw = raw.get("time", "00:00")
    time_str = time_raw[:5]
    
    # 解析带有 UTC 偏移量的开球时间，并转换为北京时间(UTC+8)
    offset_hours = 0
    if "UTC" in time_raw:
        try:
            offset_part = time_raw.split("UTC")[1].strip()
            if offset_part:
                offset_hours = int(offset_part)
        except Exception:
            pass

    if date_str and time_str:
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            dt += timedelta(hours=8 - offset_hours)
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%H:%M")
        except ValueError:
            pass
    
    group_val = raw.get("group", "")
    round_str = raw.get("round", "Matchday 1")
    round_num = 1
    if "Matchday" in round_str:
        try:
            round_num = int(round_str.replace("Matchday", "").strip())
        except ValueError:
            pass
            
    match = {
        "id": f"of26-{home_code}-{away_code}",
        "date": date_str,
        "time": time_str,
        "group": group_val or "世界杯",
        "home": home_code,
        "away": away_code,
        "round": round_num,
        "venue": raw.get("ground", ""),
    }
    match["home_name"] = home_name or home_code
    match["away_name"] = away_name or away_code
    
    if "score" in raw and raw["score"]:
        score_ft = raw["score"].get("ft")
        if isinstance(score_ft, list) and len(score_ft) >= 2:
            match["score"] = {"ft": score_ft}
            
    return match



_CACHE: dict[str, tuple[float, Any]] = {}



def _headers() -> dict:
    headers = {"User-Agent": "WorldCupPredictor/1.0"}
    raw_headers = getattr(config, "API_HEADERS", "")
    for item in raw_headers.split(";"):
        if ":" not in item:
            continue
        key, value = item.split(":", 1)
        headers[key.strip()] = value.strip()
    return headers


def fetch_json(url: str) -> Any:
    if not url:
        return None

    now = time.time()
    cached = _CACHE.get(url)
    if cached and now - cached[0] < config.DATA_CACHE_TTL_SECONDS:
        return cached[1]

    response = requests.get(url, headers=_headers(), timeout=config.DATA_API_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    _CACHE[url] = (now, data)
    return data


def _pick(data: dict, *keys, default=None):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return default


def _nested_name(value):
    if isinstance(value, dict):
        return _pick(value, "code", "abbr", "shortName", "name", "teamName")
    return value


def _as_list(payload: Any, *keys) -> list:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, list):
            return value
    data = payload.get("data")
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
    return []


def _normalize_odds(raw: dict) -> dict:
    odds = _pick(raw, "odds", "spf", "had", "hhad", default={})
    if isinstance(odds, list) and len(odds) >= 3:
        return {
            "home_win": float(odds[0]),
            "draw": float(odds[1]),
            "away_win": float(odds[2]),
        }
    if not isinstance(odds, dict):
        odds = raw

    def number(*keys):
        value = _pick(odds, *keys)
        if value in (None, ""):
            return None
        return float(value)

    normalized = {
        "home_win": number("home_win", "home", "win", "h", "spf_win", "odds_win"),
        "draw": number("draw", "d", "spf_draw", "odds_draw"),
        "away_win": number("away_win", "away", "loss", "a", "spf_loss", "odds_loss"),
    }
    if all(v is not None and v > 0 for v in normalized.values()):
        return normalized
    return {}


def normalize_match(raw: dict) -> dict:
    home = _nested_name(_pick(raw, "home", "home_team", "hostTeam", "team1"))
    away = _nested_name(_pick(raw, "away", "away_team", "guestTeam", "team2"))
    match = {
        "id": str(_pick(raw, "id", "match_id", "matchId", "num", "serial", default="")),
        "date": str(_pick(raw, "date", "match_date", "matchDate", "businessDate", default="")),
        "time": str(_pick(raw, "time", "match_time", "matchTime", "startTime", default="00:00"))[:5],
        "group": str(_pick(raw, "group", "stage", "league", "roundName", default="世界杯")),
        "home": str(_pick(raw, "home_code", "homeCode", default=home or "")),
        "away": str(_pick(raw, "away_code", "awayCode", default=away or "")),
        "round": _pick(raw, "round", "round_no", "roundNo", default=1),
        "venue": _pick(raw, "venue", "stadium", "matchCity", default=""),
    }
    match["home_name"] = str(_pick(raw, "home_name", "homeName", default=home or match["home"]))
    match["away_name"] = str(_pick(raw, "away_name", "awayName", default=away or match["away"]))
    odds = _normalize_odds(raw)
    if odds:
        match["odds"] = odds
    return match


def fetch_schedule() -> list:
    payload = fetch_json(config.SCHEDULE_API_URL)
    api_type = getattr(config, "API_TYPE", "worldcup26_ir")
    if api_type == "worldcup26_ir":
        games = payload.get("games", []) if isinstance(payload, dict) else []
        return [normalize_worldcup26_match(g) for g in games if isinstance(g, dict)]
    elif api_type == "openfootball":
        matches = payload.get("matches", []) if isinstance(payload, dict) else []
        return [normalize_openfootball_match(m) for m in matches if isinstance(m, dict)]
    matches = _as_list(payload, "matches", "matchList", "fixtures", "list", "rows")
    return [normalize_match(m) for m in matches if isinstance(m, dict)]




def fetch_odds_map() -> dict:
    payload = fetch_json(config.ODDS_API_URL)
    rows = _as_list(payload, "odds", "matches", "matchList", "list", "rows")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        match_id = str(_pick(row, "id", "match_id", "matchId", "num", "serial", default=""))
        odds = _normalize_odds(row)
        if match_id and odds:
            result[match_id] = odds
    return result
