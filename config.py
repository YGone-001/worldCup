import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Load environment variables securely from .env file (Pure Python fallback)
env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

DATA_DIR = os.path.join(BASE_DIR, "data")

# Flask
DEBUG = True
HOST = "127.0.0.1"
PORT = 5000

# Data source:
# - local: use data/*.json only
# - auto: try live API first, fallback to local
# - api: require live API data
DATA_SOURCE = os.environ.get("DATA_SOURCE", "auto").lower()
SCHEDULE_API_URL = os.environ.get("SCHEDULE_API_URL", "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json")
ODDS_API_URL = os.environ.get("ODDS_API_URL", "")
THE_ODDS_API_KEY = os.environ.get("THE_ODDS_API_KEY", "")
API_TYPE = os.environ.get("API_TYPE", "openfootball").lower()


DATA_API_TIMEOUT = float(os.environ.get("DATA_API_TIMEOUT", "8"))
DATA_CACHE_TTL_SECONDS = int(os.environ.get("DATA_CACHE_TTL_SECONDS", "300"))

# Optional headers for domestic/authorized providers. Example:
# API_HEADERS="Authorization: Bearer xxx; Referer: https://example.com"
API_HEADERS = os.environ.get("API_HEADERS", "")

# Football-data.org remains optional for future adapters.
FOOTBALL_API_KEY = os.environ.get("FOOTBALL_API_KEY", "")
FOOTBALL_API_BASE = "https://api.football-data.org/v4"

MODEL_CONFIG = {
    "base_goals_per_match": 1.35,
    "elo_weight": 0.25,
    "value_weight": 0.20,
    "ranking_weight": 0.20,
    "form_weight": 0.15,
    "history_weight": 0.10,
    "experience_weight": 0.10,
    "home_advantage": 0.04,
    "monte_carlo_runs": 10000,
    # Blend market implied probabilities from 1X2 / 胜平负 odds into the model.
    # 0 = ignore odds, 1 = use only odds implied probabilities.
    "odds_weight": float(os.environ.get("ODDS_WEIGHT", "0.20")),
}
