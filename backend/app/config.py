import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    api_sports_key: str = os.getenv("API_SPORTS_KEY", "")
    api_football_key: str = os.getenv("API_FOOTBALL_KEY", "")
    odds_api_key: str = os.getenv("ODDS_API_KEY", "")
    league_id: int = int(os.getenv("LEAGUE_ID", "262"))
    stats_season: int = int(os.getenv("STATS_SEASON", "2024"))
    odds_region: str = os.getenv("ODDS_REGION", "us")
    odds_sport_key: str = os.getenv("ODDS_SPORT_KEY", "soccer_mexico_ligamx")
    model_edge_threshold: float = float(os.getenv("MODEL_EDGE_THRESHOLD", "0.08"))
    api_sports_request_interval_seconds: float = float(os.getenv("API_SPORTS_REQUEST_INTERVAL_SECONDS", "6.1"))
    api_timeout_seconds: int = 20


settings = Settings()
