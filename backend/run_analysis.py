from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List

import requests

from app.analysis.value_model import (
    find_top_value_bets,
)
from app.analysis.odds import build_odds_snapshot_for_fixture
from app.config import settings
from app.models import Fixture
from app.services.odds_api_client import OddsApiClient
from app.services.sports_api_client import SportsApiClient
from app.utils.team_names import find_api_team_id, get_api_teams_by_name, normalize_team_name


def team_stats_cache_path() -> Path:
    return Path(__file__).resolve().parent / ".cache" / f"team_stats_{settings.league_id}_{settings.stats_season}.json"


def load_team_stats_cache(cache_path: Path) -> Dict[int, Dict[str, Any]]:
    if not cache_path.exists():
        return {}
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"No se pudo leer la caché de estadísticas {cache_path}: {error}") from error
    if not isinstance(payload, dict):
        raise RuntimeError(f"La caché de estadísticas {cache_path} debe contener un objeto JSON.")
    return {int(team_id): stats for team_id, stats in payload.items() if isinstance(stats, dict)}


def save_team_stats_cache(cache_path: Path, cache: Dict[int, Dict[str, Any]]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        temporary_path.replace(cache_path)
    except OSError as error:
        raise RuntimeError(f"No se pudo guardar la caché de estadísticas {cache_path}: {error}") from error


def normalize_fixture(raw_fixture: Dict[str, Any]) -> Fixture:
    teams = raw_fixture.get("teams", {})
    home_team = teams.get("home", {}).get("name", "Local")
    away_team = teams.get("away", {}).get("name", "Visitante")
    league = raw_fixture.get("league", {})
    fixture = raw_fixture.get("fixture", {})

    return Fixture(
        fixture_id=fixture.get("id", 0),
        home_team=home_team,
        away_team=away_team,
        kickoff=fixture.get("date", ""),
        league_name=league.get("name", "Liga MX"),
        home_team_id=teams.get("home", {}).get("id", 0),
        away_team_id=teams.get("away", {}).get("id", 0),
    )


def fixture_from_odds_event(event: Dict[str, Any], home_team_id: int, away_team_id: int) -> Fixture:
    return Fixture(
        fixture_id=0,
        home_team=str(event.get("home_team", "Local")),
        away_team=str(event.get("away_team", "Visitante")),
        kickoff=str(event.get("commence_time", "")),
        league_name="Liga MX",
        home_team_id=home_team_id,
        away_team_id=away_team_id,
    )


def find_odds_event(fixture: Fixture, odds_data: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    home_name = normalize_team_name(fixture.home_team)
    away_name = normalize_team_name(fixture.away_team)

    for event in odds_data:
        event_home = normalize_team_name(str(event.get("home_team", "")))
        event_away = normalize_team_name(str(event.get("away_team", "")))
        if event_home == home_name and event_away == away_name:
            return event
    return None


def _average_goals(stats: Dict[str, Any], category: str, venue: str) -> float | None:
    value = stats.get("goals", {}).get(category, {}).get("average", {}).get(venue)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result) or result < 0:
        return None
    return result


def attach_fixture_statistics(
    fixture: Fixture,
    sports_client: SportsApiClient,
    stats_cache: Dict[int, Dict[str, Any]],
    cache_path: Path | None = None,
) -> bool:
    if not fixture.home_team_id or not fixture.away_team_id:
        return False

    for team_id in (fixture.home_team_id, fixture.away_team_id):
        if team_id not in stats_cache:
            stats_cache[team_id] = sports_client.get_team_stats(
                team_id,
                settings.league_id,
                settings.stats_season,
            )
            if cache_path is not None and stats_cache[team_id]:
                save_team_stats_cache(cache_path, stats_cache)

    home_stats = stats_cache[fixture.home_team_id]
    away_stats = stats_cache[fixture.away_team_id]
    home_for = _average_goals(home_stats, "for", "home")
    home_against = _average_goals(home_stats, "against", "home")
    away_for = _average_goals(away_stats, "for", "away")
    away_against = _average_goals(away_stats, "against", "away")

    if any(value is None for value in (home_for, home_against, away_for, away_against)):
        return False

    fixture.recent_home_form = {
        "avg_goals_for": home_for,
        "avg_goals_against": home_against,
        "home_advantage": 1,
    }
    fixture.recent_away_form = {
        "avg_goals_for": away_for,
        "avg_goals_against": away_against,
        "away_adversity": 1,
    }
    return True


def print_fixture_summary(fixture: Fixture, odds_snapshot: List[Dict[str, object]]) -> None:
    home_form = fixture.recent_home_form
    away_form = fixture.recent_away_form
    print(f"\n{fixture.home_team} vs {fixture.away_team} | {fixture.kickoff}")
    print(
        f"Promedio de goles (API-Sports {settings.stats_season}, histórico): "
        f"local GF {home_form['avg_goals_for']:.2f} / GC {home_form['avg_goals_against']:.2f}; "
        f"visitante GF {away_form['avg_goals_for']:.2f} / GC {away_form['avg_goals_against']:.2f}"
    )
    if not odds_snapshot:
        print("Sin cuotas utilizables para los mercados 1X2 o total de goles.")
        return
    for offer in odds_snapshot:
        print(
            f"Cuota {offer['market_name']} - {offer['selection']}: "
            f"{offer['odds']:.2f} ({offer['bookmaker']})"
        )


def main() -> None:
    odds_client = OddsApiClient()
    odds_data = odds_client.get_market_odds()
    if not odds_data:
        print("The Odds API no devolvió próximos partidos o cuotas para Liga MX.")
        return

    sports_client = SportsApiClient()
    try:
        teams_raw = sports_client.get_league_teams(settings.league_id, settings.stats_season)
    except (RuntimeError, requests.RequestException) as error:
        print(f"No se pudieron cargar los equipos de API-Sports: {error}")
        print("No se generan picks sin estadísticas verificables.")
        return

    teams_by_name = get_api_teams_by_name(teams_raw)
    if not teams_by_name:
        print(f"API-Sports no devolvió equipos para la temporada histórica {settings.stats_season}.")
        return

    cache_path = team_stats_cache_path()
    try:
        stats_cache = load_team_stats_cache(cache_path)
    except RuntimeError as error:
        print(error)
        return
    all_picks: List[Dict[str, Any]] = []
    analyzed_fixtures = 0
    stats_error: Exception | None = None

    for event in odds_data[:5]:
        home_name = str(event.get("home_team", ""))
        away_name = str(event.get("away_team", ""))
        home_team_id = find_api_team_id(home_name, teams_by_name)
        away_team_id = find_api_team_id(away_name, teams_by_name)
        if home_team_id is None or away_team_id is None:
            print(f"No se pudieron relacionar ambos equipos con API-Sports: {home_name} vs {away_name}; se omite.")
            continue

        fixture = fixture_from_odds_event(event, home_team_id, away_team_id)
        try:
            has_stats = attach_fixture_statistics(fixture, sports_client, stats_cache, cache_path)
        except (RuntimeError, requests.RequestException) as error:
            stats_error = error
            print(f"API-Sports no pudo completar las estadísticas: {error}")
            print("Las estadísticas obtenidas se guardaron localmente; puedes volver a ejecutar para continuar.")
            break
        if not has_stats:
            print(
                f"Sin estadísticas de la temporada {settings.stats_season} para "
                f"{fixture.home_team} vs {fixture.away_team}; "
                "se omite para no estimar con datos inventados."
            )
            continue

        odds_snapshot = build_odds_snapshot_for_fixture(fixture, event)
        print_fixture_summary(fixture, odds_snapshot)
        analyzed_fixtures += 1
        picks = find_top_value_bets(
            fixture,
            odds_snapshot,
            threshold=settings.model_edge_threshold,
        )
        for pick in picks:
            all_picks.append(
                {
                    "fixture_id": pick.fixture_id,
                    "home_team": pick.home_team,
                    "away_team": pick.away_team,
                    "kickoff": pick.kickoff,
                    "market_name": pick.market_name,
                    "selection": pick.selection,
                    "bookmaker": pick.bookmaker,
                    "odds": pick.odds,
                    "model_probability": pick.model_probability,
                    "implied_probability": pick.implied_probability,
                    "edge": round(pick.edge, 4),
                    "expected_value": round(pick.expected_value, 4),
                    "confidence": round(pick.confidence, 4),
                }
            )

    ranked = sorted(
        all_picks,
        key=lambda item: (item["edge"], item["expected_value"], item["confidence"]),
        reverse=True,
    )[:5]

    print(f"\nTop 5 experimental | cuotas región {settings.odds_region.upper()} | stats históricas {settings.stats_season}")
    print("AVISO: datos históricos desfasados; estos resultados validan el MVP, no son recomendaciones para apostar.")
    if stats_error is not None:
        print("Resultado parcial: API-Sports limitó las consultas; solo se incluyen partidos analizados antes del error.")
    if not analyzed_fixtures:
        print("No se pudieron analizar partidos con estadísticas históricas completas y cuotas disponibles.")
        return
    if not ranked:
        print(f"Ninguna selección superó el edge mínimo de {settings.model_edge_threshold:.0%}.")
        return

    for index, pick in enumerate(ranked, start=1):
        print(
            f"{index}. {pick['home_team']} vs {pick['away_team']} | "
            f"{pick['market_name']} - {pick['selection']}"
        )
        print(
            f"   Casa: {pick['bookmaker']} | Cuota: {pick['odds']:.2f} | "
            f"Prob. modelo: {pick['model_probability']:.2%}"
        )
        print(
            f"   Prob. implícita: {pick['implied_probability']:.2%} | "
            f"Push: {pick['push_probability']:.2%} | Edge: {pick['edge']:.2%} | "
            f"EV: {pick['expected_value']:.2%}"
        )
    print("Las probabilidades son estimaciones, no garantizan resultados ni rentabilidad.")


if __name__ == "__main__":
    main()
