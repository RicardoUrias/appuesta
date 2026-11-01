from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, List
from urllib.parse import urlencode

FetchJSON = Callable[[str, Dict[str, str] | None], Awaitable[Any]]


class ProviderError(RuntimeError):
    pass


class Providers:
    def __init__(
        self,
        fetch_json: FetchJSON,
        api_sports_key: str,
        odds_api_key: str,
        odds_sport_key: str,
        odds_region: str,
    ) -> None:
        self.fetch_json = fetch_json
        self.api_sports_key = api_sports_key
        self.odds_api_key = odds_api_key
        self.odds_sport_key = odds_sport_key
        self.odds_region = odds_region

    async def get_odds(self, markets: str = "h2h,totals") -> List[Dict[str, Any]]:
        if not self.odds_api_key:
            raise ProviderError("Configura ODDS_API_KEY en los secretos del Worker.")
        params = {
            "apiKey": self.odds_api_key,
            "regions": self.odds_region,
            "markets": markets,
            "oddsFormat": "decimal",
        }
        url = f"https://api.the-odds-api.com/v4/sports/{self.odds_sport_key}/odds?{urlencode(params)}"
        payload = await self.fetch_json(url, None)
        if not isinstance(payload, list) or any(not isinstance(event, dict) for event in payload):
            raise ProviderError("The Odds API devolvió un formato de eventos inesperado.")
        return payload

    async def get_scores(self, event_ids: List[str]) -> List[Dict[str, Any]]:
        if not self.odds_api_key:
            raise ProviderError("Configura ODDS_API_KEY en los secretos del Worker.")
        params: Dict[str, str] = {"apiKey": self.odds_api_key, "daysFrom": "3"}
        if event_ids:
            params["eventIds"] = ",".join(event_ids)
        url = f"https://api.the-odds-api.com/v4/sports/{self.odds_sport_key}/scores?{urlencode(params)}"
        payload = await self.fetch_json(url, None)
        if not isinstance(payload, list) or any(not isinstance(event, dict) for event in payload):
            raise ProviderError("The Odds API devolvió un formato de resultados inesperado.")
        return payload

    async def get_api_sports(
        self,
        endpoint: str,
        params: Dict[str, str | int],
    ) -> List[Dict[str, Any]] | Dict[str, Any]:
        if not self.api_sports_key:
            raise ProviderError("Configura API_SPORTS_KEY en los secretos del Worker.")
        query = urlencode(params)
        url = f"https://v3.football.api-sports.io/{endpoint}?{query}"
        payload = await self.fetch_json(
            url,
            {
                "x-apisports-key": self.api_sports_key,
                "Accept": "application/json",
            },
        )
        if not isinstance(payload, dict):
            raise ProviderError("API-Sports devolvió una respuesta inesperada.")
        if payload.get("errors"):
            errors = payload["errors"]
            if isinstance(errors, dict) and any("limit" in str(value).casefold() for value in errors.values()):
                raise ProviderError("API-Sports alcanzó el límite de consultas; vuelve a intentar más tarde.")
            raise ProviderError("API-Sports rechazó la consulta; revisa tu clave, temporada y plan.")
        result = payload.get("response")
        if endpoint == "teams":
            if not isinstance(result, list) or any(not isinstance(team, dict) for team in result):
                raise ProviderError("API-Sports devolvió un catálogo de equipos inesperado.")
            return result
        if not isinstance(result, dict):
            raise ProviderError("API-Sports devolvió estadísticas con un formato inesperado.")
        return result

    async def get_teams(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        result = await self.get_api_sports("teams", {"league": league_id, "season": season})
        if not isinstance(result, list):
            raise ProviderError("API-Sports devolvió un catálogo de equipos inesperado.")
        return result

    async def get_team_stats(self, team_id: int, league_id: int, season: int) -> Dict[str, Any]:
        result = await self.get_api_sports(
            "teams/statistics",
            {"team": team_id, "league": league_id, "season": season},
        )
        if not isinstance(result, dict):
            raise ProviderError("API-Sports devolvió estadísticas con un formato inesperado.")
        return result
