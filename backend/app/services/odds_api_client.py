from __future__ import annotations

from typing import Any, Dict, List

import requests

from app.config import settings


class OddsApiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.odds_api_key
        if not self.api_key:
            raise RuntimeError("Configura ODDS_API_KEY en backend/.env antes de llamar a The Odds API.")
        self.base_url = "https://api.the-odds-api.com/v4"

    def get_market_odds(
        self,
        sport_key: str | None = None,
        regions: str | None = None,
        markets: str = "h2h,totals",
    ) -> List[Dict[str, Any]]:
        requested_sport = sport_key or settings.odds_sport_key
        requested_region = regions or settings.odds_region

        url = f"{self.base_url}/sports/{requested_sport}/odds"
        params = {
            "apiKey": self.api_key,
            "regions": requested_region,
            "markets": markets,
            "oddsFormat": "decimal",
        }

        try:
            response = requests.get(url, params=params, timeout=settings.api_timeout_seconds)
        except requests.RequestException:
            raise RuntimeError("No se pudo conectar con The Odds API; revisa la red y el tiempo de espera.") from None

        if response.status_code >= 400:
            raise RuntimeError(
                f"The Odds API respondió HTTP {response.status_code}; revisa la clave, región, deporte y cuota disponible."
            )

        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("The Odds API devolvió un formato inesperado; se esperaba una lista de eventos.")
        return payload

    def get_best_offer_for_match(self, match_name: str, odds_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        best_offer: Dict[str, Any] = {"bookmaker": "N/A", "market": "N/A", "odds": 0.0}

        for item in odds_data:
            title = item.get("home_team", "") + " vs " + item.get("away_team", "")
            if match_name.lower() not in title.lower():
                continue

            for bookmaker in item.get("bookmakers", []):
                for market in bookmaker.get("markets", []):
                    for outcome in market.get("outcomes", []):
                        if outcome.get("price", 0) > best_offer["odds"]:
                            best_offer = {
                                "bookmaker": bookmaker.get("title", "N/A"),
                                "market": market.get("key", "N/A"),
                                "odds": float(outcome.get("price", 0)),
                                "selection": outcome.get("name", "N/A"),
                            }

        return best_offer
