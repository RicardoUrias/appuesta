from __future__ import annotations

import time
from typing import Any, Dict, List

import requests

from app.config import settings


class SportsApiClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.api_sports_key
        if not self.api_key:
            raise RuntimeError("Configura API_SPORTS_KEY en backend/.env antes de llamar a API-Sports.")
        self.base_url = "https://v3.football.api-sports.io"
        self.headers = {
            "x-apisports-key": self.api_key,
            "Accept": "application/json",
        }
        self._last_request_at: float | None = None

    def _get(self, endpoint: str, params: Dict[str, Any]) -> Any:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            wait = settings.api_sports_request_interval_seconds - elapsed
            if wait > 0:
                time.sleep(wait)

        response = requests.get(
            f"{self.base_url}/{endpoint}",
            headers=self.headers,
            params=params,
            timeout=settings.api_timeout_seconds,
        )
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        payload = response.json()
        if payload.get("errors"):
            raise RuntimeError(f"API-Sports reportó errores al consultar {endpoint}: {payload['errors']}")
        return payload.get("response", [])

    def get_next_fixtures(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        params = {
            "league": league_id,
            "season": season,
            "next": 10,
            "status": "NS",
        }
        return self._get("fixtures", params)

    def get_league_teams(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        params = {"league": league_id, "season": season}
        return self._get("teams", params)

    def get_h2h(self, home_id: int, away_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        params = {
            "h2h": f"{home_id}-{away_id}",
            "limit": limit,
        }
        return self._get("fixtures/headtohead", params)

    def get_team_stats(self, team_id: int, league_id: int, season: int) -> Dict[str, Any]:
        params = {"team": team_id, "league": league_id, "season": season}
        return self._get("teams/statistics", params)

    def get_fixture_statistics(self, fixture_id: int) -> Dict[str, Any]:
        params = {"fixture": fixture_id}
        return self._get("fixtures/statistics", params)
